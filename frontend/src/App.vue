<template>
  <!-- 打印视图使用独立的无框布局 -->
  <router-view v-if="$route.meta.plain" />

  <el-container v-else class="layout">
    <el-aside width="200px" class="sidebar desktop-only">
      <div class="logo" @click="$router.push('/')">
        <span class="logo-icon">智</span>
        <span class="logo-text">智析错题本</span>
      </div>
      <el-menu :default-active="$route.path" router class="menu">
        <el-menu-item index="/">📕 错题本</el-menu-item>
        <el-menu-item index="/papers">📝 试卷分析</el-menu-item>
        <el-menu-item index="/plan">📅 学习计划</el-menu-item>
        <el-menu-item index="/graph">🕸️ 知识图谱</el-menu-item>
        <el-menu-item index="/settings">⚙️ 设置</el-menu-item>
      </el-menu>
      <div class="sidebar-foot muted">AI + 开源 · 中学生错题管理</div>
    </el-aside>

    <el-container>
      <el-header class="mobile-topbar mobile-only" height="52px">
        <span class="logo-text strong">智析错题本</span>
        <el-button text @click="drawer = true">☰ 菜单</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <el-drawer v-model="drawer" size="200px" :with-header="false" class="mobile-only">
      <el-menu :default-active="$route.path" router @select="drawer = false">
        <el-menu-item index="/">📕 错题本</el-menu-item>
        <el-menu-item index="/papers">📝 试卷分析</el-menu-item>
        <el-menu-item index="/plan">📅 学习计划</el-menu-item>
        <el-menu-item index="/graph">🕸️ 知识图谱</el-menu-item>
        <el-menu-item index="/settings">⚙️ 设置</el-menu-item>
      </el-menu>
    </el-drawer>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
const drawer = ref(false)
</script>

<style scoped>
.layout { min-height: 100vh; }
.sidebar {
  background: #fff; border-right: 1px solid #e4e7ed;
  display: flex; flex-direction: column; position: fixed; top: 0; bottom: 0; left: 0; z-index: 10;
}
.logo { display: flex; align-items: center; gap: 8px; padding: 18px 16px 12px; cursor: pointer; }
.logo-icon {
  width: 32px; height: 32px; border-radius: 8px; background: #409eff; color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 18px;
}
.logo-text { font-weight: 700; font-size: 16px; }
.strong { font-weight: 700; }
.menu { border-right: none; flex: 1; }
.sidebar-foot { padding: 14px 16px; }
.main { padding: 0; }
.mobile-topbar {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-bottom: 1px solid #e4e7ed;
}
.desktop-only { display: flex; }
.mobile-only { display: none; }
.mobile-only :deep(.el-menu) { border-right: none; }
@media (max-width: 768px) {
  .desktop-only { display: none; }
  .mobile-only { display: flex; }
  .main { margin-left: 0; }
}
@media (min-width: 769px) {
  .main { margin-left: 200px; }
}
</style>
