<template>
  <header class="header">
    <div class="header-left">
      <router-link to="/governance" class="logo">
        <div class="logo-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false">
            <path
              d="M12 3.2 5.2 5.8v5.1c0 4.3 2.7 8.2 6.8 9.9 4.1-1.7 6.8-5.6 6.8-9.9V5.8L12 3.2Z"
            />
            <path d="M9.1 12.1 11 14l4-4" />
          </svg>
        </div>
        <span>内容安全治理平台</span>
      </router-link>
      <nav class="nav-tabs">
        <router-link to="/data-input" class="nav-tab" active-class="active">
          <span>输入数据治理</span>
        </router-link>
        <router-link to="/output" class="nav-tab" active-class="active">
          <span>输出内容治理</span>
        </router-link>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts"></script>

<style scoped>
.header {
  background: linear-gradient(135deg, #0d47a1 0%, #1565c0 100%);
  border-bottom: 2px solid #0d47a1;
  padding: 0 24px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 12px rgba(13, 71, 161, 0.2);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
  min-width: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  text-decoration: none;
  white-space: nowrap;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.logo-icon svg {
  width: 22px;
  height: 22px;
  fill: none;
  stroke: #fff;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.nav-tabs {
  display: flex;
  gap: 4px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.nav-tabs::-webkit-scrollbar {
  display: none;
}

.nav-tab {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.78);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
  text-decoration: none;
  white-space: nowrap;
}

.nav-tab:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.nav-tab.active {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  font-weight: 800;
}

.nav-tab.active::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 50%;
  transform: translateX(-50%);
  width: 18px;
  height: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
}

@media (max-width: 1120px) {
  .header {
    padding: 0 16px;
  }
}

@media (max-width: 900px) {
  .header {
    height: 56px;
  }

  .header-left {
    gap: 14px;
  }

  .logo {
    font-size: 16px;
  }

  .nav-tab {
    padding: 8px 12px;
    font-size: 15px;
  }
}
</style>
