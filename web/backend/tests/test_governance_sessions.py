import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import BenchmarkAsset, GovernanceCompletionRecord, GovernanceTask
from app.db.session import AsyncSessionLocal
from app.services.benchmark_topic1_value_qa_sample_service import BenchmarkTopic1ValueQaSampleService
from app.services.governance_assistant import OpenAiCompatibleInterpreter, _parse_intent


OFFICIAL_VALUE_QA_ASSET_ID = "topic1_value_qa_marked_merged_round3"


def user_contents(messages):
    return [message["content"] for message in messages if message["role"] == "user"]


def assistant_messages(messages):
    return [message for message in messages if message["role"] == "assistant"]


def _value_qa_manifest(with_dimensions: bool) -> dict:
    manifest = {
        "benchmark_type": "value_qa",
        "sample_count": 222,
        "group_count": 74,
        "quality_level_distribution": {"high": 100, "medium": 80, "low": 42},
    }
    if with_dimensions:
        manifest["primary_dimension_distribution"] = {"多样性": 120, "安全性": 102}
        manifest["secondary_dimension_distribution"] = {"文化适配": 150, "风险规避": 72}
    return manifest


async def _seed_value_qa_asset(with_dimensions: bool = True) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(BenchmarkAsset).where(BenchmarkAsset.asset_id == OFFICIAL_VALUE_QA_ASSET_ID)
        )
        if existing.scalar_one_or_none() is not None:
            return
        db.add(
            BenchmarkAsset(
                asset_id=OFFICIAL_VALUE_QA_ASSET_ID,
                task_id="task-governance-test",
                source_mode="prerun_snapshot",
                name="Topic1 value_qa marked merged with round3 QC",
                manifest_json=json.dumps(_value_qa_manifest(with_dimensions), ensure_ascii=False),
                artifact_dir="/tmp/governance-test",
                artifact_zip_path="/tmp/governance-test/bundle.zip",
                artifact_sha256="0" * 64,
                source_repo="Project_1_Sample_evaluation_Generation",
                source_commit="9826945",
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_first_nonempty_request_creates_recoverable_session(client):
    client_id = str(uuid4())
    headers = {"X-Governance-Client-Id": client_id}

    empty = await client.get("/api/governance/sessions", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["data"]["items"] == []

    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "查看价值语料\n构成"},
    )
    assert created.status_code == 201
    session = created.json()["data"]
    assert session["title"] == "查看价值语料 构成"
    assert session["domain"] == "input"
    assert user_contents(session["messages"]) == ["查看价值语料\n构成"]
    assistant = assistant_messages(session["messages"])
    assert len(assistant) == 1
    assert assistant[0]["kind"] == "value_corpus_overview"
    assert assistant[0]["payload"]["available"] is False

    restored = await client.get(
        f"/api/governance/sessions/{session['session_id']}", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["messages"] == session["messages"]

    history = await client.get("/api/governance/sessions", headers=headers)
    assert [item["session_id"] for item in history.json()["data"]["items"]] == [
        session["session_id"]
    ]


@pytest.mark.asyncio
async def test_turns_keep_message_order_and_session_domain(client):
    client_id = str(uuid4())
    headers = {"X-Governance-Client-Id": client_id}
    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "output", "prompt": "查看风险预跑记录"},
    )
    session_id = created.json()["data"]["session_id"]

    wrong_domain = await client.post(
        f"/api/governance/sessions/{session_id}/turns",
        headers=headers,
        json={"domain": "input", "prompt": "查看价值语料"},
    )
    assert wrong_domain.status_code == 400

    added = await client.post(
        f"/api/governance/sessions/{session_id}/turns",
        headers=headers,
        json={"domain": "output", "prompt": "按时间筛选"},
    )
    assert added.status_code == 201
    assert added.json()["data"]["domain"] == "output"

    restored = await client.get(f"/api/governance/sessions/{session_id}", headers=headers)
    assert restored.json()["data"]["domain"] == "output"
    assert user_contents(restored.json()["data"]["messages"]) == [
        "查看风险预跑记录",
        "按时间筛选",
    ]


@pytest.mark.asyncio
async def test_soft_delete_hides_session_only_from_its_client(client):
    owner = {"X-Governance-Client-Id": str(uuid4())}
    other = {"X-Governance-Client-Id": str(uuid4())}
    created = await client.post(
        "/api/governance/sessions",
        headers=owner,
        json={"domain": "input", "prompt": "查看语料"},
    )
    session_id = created.json()["data"]["session_id"]

    assert (
        await client.get(f"/api/governance/sessions/{session_id}", headers=other)
    ).status_code == 404
    assert (
        await client.delete(f"/api/governance/sessions/{session_id}", headers=other)
    ).status_code == 404

    deleted = await client.delete(f"/api/governance/sessions/{session_id}", headers=owner)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_at"]
    assert (await client.get("/api/governance/sessions", headers=owner)).json()["data"]["items"] == []
    assert (
        await client.get(f"/api/governance/sessions/{session_id}", headers=owner)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/governance/sessions/{session_id}/turns",
            headers=owner,
            json={"domain": "input", "prompt": "继续"},
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_empty_request_does_not_create_session_and_title_is_bounded(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}
    rejected = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": " \n\t "},
    )
    assert rejected.status_code == 400
    assert (await client.get("/api/governance/sessions", headers=headers)).json()["data"]["items"] == []

    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "甲" * 40},
    )
    assert created.json()["data"]["title"] == "甲" * 28


@pytest.mark.asyncio
async def test_client_registration_is_repeatable_without_empty_sessions(client):
    client_id = str(uuid4())
    first = await client.post("/api/governance/clients", json={"client_id": client_id})
    second = await client.post("/api/governance/clients", json={"client_id": client_id})
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["client_id"] == client_id
    assert second.json()["data"]["client_id"] == client_id
    history = await client.get(
        "/api/governance/sessions", headers={"X-Governance-Client-Id": client_id}
    )
    assert history.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_history_is_ordered_by_recent_activity_and_bounded(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}
    first = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "第一项"},
    )
    second = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "output", "prompt": "第二项"},
    )
    first_id = first.json()["data"]["session_id"]
    second_id = second.json()["data"]["session_id"]
    await client.post(
        f"/api/governance/sessions/{first_id}/turns",
        headers=headers,
        json={"domain": "input", "prompt": "继续第一项"},
    )

    page = await client.get("/api/governance/sessions?limit=1&offset=0", headers=headers)
    assert page.json()["data"]["total"] == 2
    assert [item["session_id"] for item in page.json()["data"]["items"]] == [first_id]
    next_page = await client.get("/api/governance/sessions?limit=1&offset=1", headers=headers)
    assert [item["session_id"] for item in next_page.json()["data"]["items"]] == [second_id]


@pytest.mark.asyncio
async def test_fresh_app_start_creates_governance_schema_for_public_api(client):
    from app.db.base import Base
    from app.db.session import engine
    from app.main import app

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    async with app.router.lifespan_context(app):
        created = await client.post(
            "/api/governance/sessions",
            headers={"X-Governance-Client-Id": str(uuid4())},
            json={"domain": "input", "prompt": "查看价值语料构成"},
        )
    assert created.status_code == 201
    assert created.json()["data"]["messages"][0]["content"] == "查看价值语料构成"


@pytest.mark.asyncio
async def test_retrying_same_request_does_not_duplicate_session_or_message(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}
    first_request = {
        "domain": "input",
        "prompt": "查看价值语料构成",
        "request_id": str(uuid4()),
    }
    first = await client.post("/api/governance/sessions", headers=headers, json=first_request)
    repeated = await client.post("/api/governance/sessions", headers=headers, json=first_request)
    session_id = first.json()["data"]["session_id"]
    assert repeated.json()["data"]["session_id"] == session_id
    assert (await client.get("/api/governance/sessions", headers=headers)).json()["data"]["total"] == 1

    next_request = {
        "domain": "input",
        "prompt": "再看一组",
        "request_id": str(uuid4()),
    }
    next_url = f"/api/governance/sessions/{session_id}/turns"
    added = await client.post(next_url, headers=headers, json=next_request)
    added_again = await client.post(next_url, headers=headers, json=next_request)
    assert added_again.json()["data"] == added.json()["data"]
    detail = await client.get(f"/api/governance/sessions/{session_id}", headers=headers)
    assert user_contents(detail.json()["data"]["messages"]) == [
        "查看价值语料构成",
        "再看一组",
    ]


@pytest.mark.asyncio
async def test_retry_with_changed_prompt_returns_original_session(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}
    request_id = str(uuid4())
    first = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "原始请求", "request_id": request_id},
    )
    retried = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "改动后的请求", "request_id": request_id},
    )
    assert retried.status_code == 201
    assert retried.json()["data"]["session_id"] == first.json()["data"]["session_id"]
    detail = await client.get(
        f"/api/governance/sessions/{first.json()['data']['session_id']}", headers=headers
    )
    assert user_contents(detail.json()["data"]["messages"]) == ["原始请求"]
    assert (await client.get("/api/governance/sessions", headers=headers)).json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_same_request_id_is_scoped_per_client(client):
    request_id = str(uuid4())
    first = await client.post(
        "/api/governance/sessions",
        headers={"X-Governance-Client-Id": str(uuid4())},
        json={"domain": "input", "prompt": "第一客户端", "request_id": request_id},
    )
    second = await client.post(
        "/api/governance/sessions",
        headers={"X-Governance-Client-Id": str(uuid4())},
        json={"domain": "output", "prompt": "第二客户端", "request_id": request_id},
    )
    assert second.status_code == 201
    assert first.json()["data"]["session_id"] != second.json()["data"]["session_id"]
    assert first.json()["data"]["messages"][0]["content"] == "第一客户端"
    assert second.json()["data"]["messages"][0]["content"] == "第二客户端"


@pytest.mark.asyncio
async def test_append_retry_with_changed_prompt_returns_original_message(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}
    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "查看价值语料"},
    )
    session_id = created.json()["data"]["session_id"]
    request_id = str(uuid4())
    added = await client.post(
        f"/api/governance/sessions/{session_id}/turns",
        headers=headers,
        json={"domain": "input", "prompt": "继续第一项", "request_id": request_id},
    )
    retried = await client.post(
        f"/api/governance/sessions/{session_id}/turns",
        headers=headers,
        json={"domain": "input", "prompt": "改动后的追加", "request_id": request_id},
    )
    assert retried.json()["data"] == added.json()["data"]
    detail = await client.get(f"/api/governance/sessions/{session_id}", headers=headers)
    assert user_contents(detail.json()["data"]["messages"]) == [
        "查看价值语料",
        "继续第一项",
    ]


@pytest.mark.asyncio
async def test_value_corpus_overview_returns_structured_payload(client):
    await _seed_value_qa_asset()
    headers = {"X-Governance-Client-Id": str(uuid4())}
    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "查看价值语料构成"},
    )
    assert created.status_code == 201
    assistant = assistant_messages(created.json()["data"]["messages"])
    assert len(assistant) == 1
    message = assistant[0]
    assert message["kind"] == "value_corpus_overview"
    payload = message["payload"]
    assert payload["available"] is True
    assert payload["capability"] == "value_corpus_overview"
    assert payload["capability_version"] == "v1"
    assert payload["sample_count"] == 222
    assert payload["group_count"] == 74
    assert payload["quality_level_distribution"] == {"high": 100, "medium": 80, "low": 42}
    assert payload["source_refs"] == [
        {
            "ref_type": "value_qa_asset",
            "ref_id": OFFICIAL_VALUE_QA_ASSET_ID,
            "name": "Topic1 value_qa marked merged with round3 QC",
            "source_repo": "Project_1_Sample_evaluation_Generation",
            "source_commit": "9826945",
        }
    ]
    assert "样本总数" in message["content"]


@pytest.mark.asyncio
async def test_value_corpus_overview_aggregates_dimensions_from_groups(client, monkeypatch):
    await _seed_value_qa_asset(with_dimensions=False)

    async def fake_list_groups(self, db, **kwargs):
        return {
            "groups": [
                {"primary_dimension": "多样性", "secondary_dimension": "文化适配"},
                {"primary_dimension": "多样性", "secondary_dimension": "风险规避"},
                {"primary_dimension": "安全性", "secondary_dimension": "文化适配"},
            ]
        }

    monkeypatch.setattr(BenchmarkTopic1ValueQaSampleService, "list_groups", fake_list_groups)
    headers = {"X-Governance-Client-Id": str(uuid4())}
    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "查看价值语料构成"},
    )
    assert created.status_code == 201
    message = assistant_messages(created.json()["data"]["messages"])[0]
    payload = message["payload"]
    assert payload["primary_dimension_distribution"] == {"多样性": 2, "安全性": 1}
    assert payload["secondary_dimension_distribution"] == {"文化适配": 2, "风险规避": 1}


@pytest.mark.asyncio
async def test_governance_task_and_completion_record_persisted(client):
    await _seed_value_qa_asset()
    headers = {"X-Governance-Client-Id": str(uuid4())}
    await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "查看价值语料构成"},
    )

    async with AsyncSessionLocal() as db:
        task = (
            await db.execute(select(GovernanceTask).order_by(GovernanceTask.id.desc()))
        ).scalars().first()
        completion = (
            await db.execute(select(GovernanceCompletionRecord))
        ).scalars().first()

    assert task is not None
    assert task.provider == "stub"
    assert task.model == "stub-governance-model"
    assert task.capability == "value_corpus_overview"
    assert task.parse_status == "ok"
    assert task.status == "completed"
    assert task.latency_ms >= 0

    assert completion is not None
    assert completion.task_id == task.task_id
    assert completion.capability == "value_corpus_overview"
    assert completion.capability_version == "v1"
    snapshot = json.loads(completion.result_snapshot_json)
    assert snapshot["sample_count"] == 222
    assert json.loads(completion.source_refs_json)[0]["ref_id"] == OFFICIAL_VALUE_QA_ASSET_ID


@pytest.mark.asyncio
async def test_fabricated_or_cross_domain_request_is_boundary_limited(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}

    fabricated = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "帮我导出一份报告"},
    )
    assistant = assistant_messages(fabricated.json()["data"]["messages"])
    assert len(assistant) == 1
    assert assistant[0]["kind"] == "boundary"

    cross_domain = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "output", "prompt": "查看价值语料构成"},
    )
    assistant = assistant_messages(cross_domain.json()["data"]["messages"])
    assert len(assistant) == 1
    assert assistant[0]["kind"] == "boundary"


@pytest.mark.asyncio
async def test_ambiguous_prompt_is_clarified(client):
    headers = {"X-Governance-Client-Id": str(uuid4())}
    created = await client.post(
        "/api/governance/sessions",
        headers=headers,
        json={"domain": "input", "prompt": "帮我看看最近的情况"},
    )
    assistant = assistant_messages(created.json()["data"]["messages"])
    assert len(assistant) == 1
    assert assistant[0]["kind"] == "clarify"
    assert assistant[0]["content"]


def test_parse_intent_accepts_plain_json():
    intent, status, _ = _parse_intent('{"kind":"clarify","message":"请说明"}')
    assert status == "ok"
    assert intent is not None
    assert intent.kind == "clarify"
    assert intent.message == "请说明"


def test_parse_intent_strips_markdown_fence():
    content = '```json\n{"kind":"boundary","message":"out of scope"}\n```'
    intent, status, _ = _parse_intent(content)
    assert status == "ok"
    assert intent is not None
    assert intent.kind == "boundary"


def test_parse_intent_extracts_object_from_prose():
    content = '好的，结果是：\n{"kind":"execute","capability":"value_corpus_overview","parameters":{}}\n以上。'
    intent, status, _ = _parse_intent(content)
    assert status == "ok"
    assert intent is not None
    assert intent.kind == "execute"
    assert intent.capability == "value_corpus_overview"


def test_parse_intent_rejects_empty_and_non_json():
    assert _parse_intent("")[1] == "empty"
    assert _parse_intent("这是纯文本，没有 JSON")[1] == "json_invalid"


class _ScriptedChatClient:
    """Records chat calls and returns a fixed assistant JSON object."""

    def __init__(self, posts: list[str], content: str) -> None:
        self._posts = posts
        self._content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json=None, headers=None):  # noqa: A002
        self._posts.append(url)
        return _ScriptedChatResponse(self._content)


class _ScriptedChatResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def _scripted_client(posts: list[str], content: str):
    def _client(*_args, **_kwargs):
        return _ScriptedChatClient(posts, content)

    return _client


_O0_CLARIFY = (
    '{"kind":"clarify","message":'
    '"请补充您要查看的风险语料构成的具体范围：'
    '例如是否要浏览风险安全系统预跑记录。"}'
)


@pytest.mark.asyncio
async def test_output_domain_risk_corpus_wording_is_boundary_without_asking_model(
    monkeypatch,
):
    """O0: 输出域里的「查看风险语料构成」是输入语料能力，不能交给模型澄清成系统预跑范围。"""
    posts: list[str] = []
    monkeypatch.setattr(
        "app.services.governance_assistant.httpx.AsyncClient",
        _scripted_client(posts, _O0_CLARIFY),
    )
    interpreter = OpenAiCompatibleInterpreter(
        "deepseek", "https://example.invalid", "deepseek-v4-pro"
    )
    result = await interpreter.interpret("output", "查看风险语料构成")

    assert result.intent is not None
    assert result.intent.kind == "boundary"
    assert result.intent.message is not None
    assert "当前为输出内容治理，无法执行输入语料能力" in result.intent.message
    assert "查看最近的风险安全评测系统预跑记录" in result.intent.message
    assert "查看最近的文化多样性系统预跑记录" in result.intent.message
    assert posts == []


@pytest.mark.asyncio
async def test_live_interpreter_still_asks_model_for_in_domain_prompts(
    monkeypatch,
):
    posts: list[str] = []
    monkeypatch.setattr(
        "app.services.governance_assistant.httpx.AsyncClient",
        _scripted_client(
            posts,
            '{"kind":"execute","capability":"risk_system_record_search","parameters":{}}',
        ),
    )
    interpreter = OpenAiCompatibleInterpreter(
        "deepseek", "https://example.invalid", "deepseek-v4-pro"
    )

    output = await interpreter.interpret("output", "查看最近的风险安全评测系统预跑记录")
    risk_overview = await interpreter.interpret("input", "查看风险语料构成")

    assert output.intent is not None and output.intent.kind == "execute"
    assert output.intent.capability == "risk_system_record_search"
    assert risk_overview.intent is not None and risk_overview.intent.kind == "execute"
    assert len(posts) == 2


@pytest.mark.asyncio
async def test_output_session_shows_input_corpus_boundary(client, monkeypatch):
    posts: list[str] = []
    monkeypatch.setattr(
        "app.services.governance_session_service.get_assistant_interpreter",
        lambda: OpenAiCompatibleInterpreter(
            "deepseek", "https://example.invalid", "deepseek-v4-pro"
        ),
    )
    monkeypatch.setattr(
        "app.services.governance_assistant.httpx.AsyncClient",
        _scripted_client(posts, _O0_CLARIFY),
    )
    created = await client.post(
        "/api/governance/sessions",
        headers={"X-Governance-Client-Id": str(uuid4())},
        json={"domain": "output", "prompt": "查看风险语料构成"},
    )
    assert created.status_code == 201
    assistant = assistant_messages(created.json()["data"]["messages"])
    assert len(assistant) == 1
    assert assistant[0]["kind"] == "boundary"
    assert "当前为输出内容治理，无法执行输入语料能力" in assistant[0]["content"]
    assert "查看最近的风险安全评测系统预跑记录" in assistant[0]["content"]
    assert "查看最近的文化多样性系统预跑记录" in assistant[0]["content"]
    assert posts == []