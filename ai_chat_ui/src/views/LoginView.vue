<template>
  <div class="login-container" :class="{ 'register-mode': !isLogin }">
    <el-card class="login-card">
      <h2 class="login-title">{{ isLogin ? '用户登录' : '用户注册' }}</h2>
      
      <el-form 
        :model="form" 
        :rules="rules" 
        ref="loginForm"
        @submit.prevent="handleSubmit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            prefix-icon="el-icon-user"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="el-icon-lock"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button 
            type="primary" 
            native-type="submit"
            :loading="loading"
            class="submit-btn"
          >
            {{ isLogin ? '登录' : '注册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="switch-mode">
        <el-link type="info" @click="toggleMode">
          {{ isLogin ? '没有账号？立即注册' : '已有账号？立即登录' }}
        </el-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const router = useRouter()

const isLogin = ref(true)
const loading = ref(false)
const form = ref({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
  ]
}

const toggleMode = () => {
  isLogin.value = !isLogin.value
}

const handleSubmit = async () => {
  loading.value = true
  try {
    const success = isLogin.value 
      ? await authStore.login(form.value.username, form.value.password)
      : await authStore.register(form.value.username, form.value.password)
    
    if (success) {
      ElMessage.success(isLogin.value ? '登录成功' : '注册成功')
      router.push('/')
    }
  } catch (error) {
    const errorMsg = error.response?.data?.message || 
                    (isLogin.value ? '登录失败，请检查用户名和密码' : '注册失败，用户名可能已存在')
    ElMessage.error(errorMsg)
    
    // 如果是注册失败且用户名已存在，跳转到登录
    if (!isLogin.value && error.response?.data?.action === 'redirect_to_login') {
      isLogin.value = true
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, var(--bg-color-1) 0%, var(--bg-color-2) 100%);
  transition: all 0.5s ease;
}

.login-card {
  width: 400px;
  padding: 30px;
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.9);
  transition: all 0.3s ease;
}

.login-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.15);
}

.login-title {
  text-align: center;
  margin-bottom: 30px;
  color: var(--title-color);
  font-size: 24px;
  font-weight: bold;
  transition: all 0.3s ease;
}

.submit-btn {
  width: 100%;
  background-color: var(--btn-color);
  border: none;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  opacity: 0.9;
  transform: translateY(-2px);
}

.switch-mode {
  text-align: center;
  margin-top: 20px;
}

:root {
  --bg-color-1: #f5f7fa;
  --bg-color-2: #c3cfe2;
  --title-color: #409EFF;
  --btn-color: #409EFF;
}

.login-container.register-mode {
  --bg-color-1: #f3e7e9;
  --bg-color-2: #e3eeff;
  --title-color: #FF6B6B;
  --btn-color: #FF6B6B;
}
</style>
