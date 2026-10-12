<template>
  <el-result icon="warning" title="页面不存在" sub-title="请检查地址，或返回系统首页">
    <template #extra><el-button type="primary" @click="$router.push('/dashboard')">返回 Dashboard</el-button><el-button @click="$router.back()">返回上一页</el-button></template>
  </el-result>
</template>
