<template>
  <div class="auth-container" :class="{ 'register-mode': !isLogin }">
    <div class="auth-background">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
      <div class="shape shape-4"></div>
    </div>

    <div class="auth-card">
      <div class="auth-header">
        <h2>{{ isLogin ? "欢迎回来" : "创建账户" }}</h2>
        <p>{{ isLogin ? "请登录您的账户" : "注册新账户开始使用" }}</p>
      </div>

      <el-form
        :model="form"
        :rules="rules"
        ref="loginForm"
        @submit.prevent="handleSubmit"
        class="auth-form"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            class="custom-input"
          >
            <template #prefix>
              <i class="icon-user"></i>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            class="custom-input"
            show-password
          >
            <template #prefix>
              <i class="icon-lock"></i>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            class="submit-btn"
          >
            {{ isLogin ? "登 录" : "注 册" }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        <span>{{ isLogin ? "新用户?" : "已有账户?" }}</span>
        <el-link type="primary" @click="toggleMode" class="switch-link">
          {{ isLogin ? "立即注册" : "立即登录" }}
        </el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useAuthStore } from "../stores/auth";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

const authStore = useAuthStore();
const router = useRouter();

const isLogin = ref(true);
const loading = ref(false);
const form = ref({
  username: "",
  password: "",
});

const rules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 3, max: 20, message: "长度在 3 到 20 个字符", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, max: 20, message: "长度在 6 到 20 个字符", trigger: "blur" },
  ],
};

const toggleMode = () => {
  isLogin.value = !isLogin.value;
};

const handleSubmit = async () => {
  loading.value = true;
  try {
    const success = isLogin.value
      ? await authStore.login(form.value.username, form.value.password)
      : await authStore.register(form.value.username, form.value.password);

    if (success) {
      ElMessage.success(isLogin.value ? "登录成功" : "注册成功");
      router.push("/");
    }
  } catch (error) {
    const errorMsg =
      error.response?.data?.message ||
      (isLogin.value
        ? "登录失败，请检查用户名和密码"
        : "注册失败，用户名可能已存在");
    ElMessage.error(errorMsg);

    if (
      !isLogin.value &&
      error.response?.data?.action === "redirect_to_login"
    ) {
      isLogin.value = true;
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped lang="scss">
@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap");

$primary-color: #4361ee;
$secondary-color: #3f37c9;
$accent-color: #4cc9f0;
$text-color: #2b2d42;
$light-color: #f8f9fa;
$dark-color: #212529;
$success-color: #4caf50;
$error-color: #f44336;

$login-bg: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
$register-bg: linear-gradient(135deg, #fff1eb 0%, #ace0f9 100%);

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: "Poppins", sans-serif;
}

.auth-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: $login-bg;
  transition: all 0.5s ease;
  overflow: hidden;

  &.register-mode {
    background: $register-bg;

    .auth-card {
      border-color: rgba($accent-color, 0.2);
    }

    .submit-btn {
      background: linear-gradient(
        135deg,
        $accent-color 0%,
        $secondary-color 100%
      );
    }

    .shape-1 {
      background: rgba($accent-color, 0.8);
    }

    .shape-2 {
      background: rgba($secondary-color, 0.8);
    }
  }
}

.auth-background {
  position: absolute;
  width: 100%;
  height: 100%;

  .shape {
    position: absolute;
    border-radius: 50%;
    filter: blur(60px);
    opacity: 0.6;
    z-index: 0;

    &-1 {
      width: 300px;
      height: 300px;
      background: rgba($primary-color, 0.8);
      top: -50px;
      left: -50px;
      animation: float 8s infinite ease-in-out;
    }

    &-2 {
      width: 400px;
      height: 400px;
      background: rgba($secondary-color, 0.8);
      bottom: -100px;
      right: -100px;
      animation: float 10s infinite ease-in-out reverse;
    }

    &-3 {
      width: 200px;
      height: 200px;
      background: rgba($accent-color, 0.6);
      top: 30%;
      right: 20%;
      animation: float 7s infinite ease-in-out;
    }

    &-4 {
      width: 250px;
      height: 250px;
      background: rgba(255, 255, 255, 0.8);
      bottom: 20%;
      left: 20%;
      animation: float 9s infinite ease-in-out reverse;
    }
  }
}

.auth-card {
  position: relative;
  width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 20px;
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  z-index: 1;
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  overflow: hidden;

  &::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 5px;
    background: linear-gradient(90deg, $primary-color 0%, $accent-color 100%);
  }

  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  }
}

.auth-header {
  text-align: center;
  margin-bottom: 30px;

  h2 {
    color: $text-color;
    font-size: 28px;
    font-weight: 600;
    margin-bottom: 8px;
  }

  p {
    color: lighten($text-color, 20%);
    font-size: 14px;
    font-weight: 400;
  }
}

.auth-form {
  .el-form-item {
    margin-bottom: 25px;

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.custom-input {
  :deep(.el-input__wrapper) {
    background: rgba(255, 255, 255, 0.8);
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    padding: 12px 15px;
    transition: all 0.3s ease;

    &:hover {
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }

    &.is-focus {
      box-shadow: 0 4px 15px rgba($primary-color, 0.2);
    }
  }

  :deep(.el-input__prefix) {
    display: flex;
    align-items: center;
    margin-right: 10px;

    i {
      color: lighten($text-color, 30%);
      font-size: 18px;
    }
  }
}

.submit-btn {
  width: 100%;
  height: 48px;
  background: linear-gradient(135deg, $primary-color 0%, $secondary-color 100%);
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 1px;
  box-shadow: 0 4px 15px rgba($primary-color, 0.3);
  transition: all 0.3s ease;
  margin-top: 10px;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba($primary-color, 0.4);
  }

  &:active {
    transform: translateY(1px);
  }
}

.auth-footer {
  text-align: center;
  margin-top: 25px;
  font-size: 14px;
  color: lighten($text-color, 20%);

  .switch-link {
    margin-left: 5px;
    font-weight: 500;
  }
}

.icon-user,
.icon-lock {
  display: inline-block;
  width: 20px;
  height: 20px;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.icon-user {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%236b7280'%3E%3Cpath d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/%3E%3C/svg%3E");
}

.icon-lock {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%236b7280'%3E%3Cpath d='M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z'/%3E%3C/svg%3E");
}

@keyframes float {
  0% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(20px, 20px);
  }
  100% {
    transform: translate(0, 0);
  }
}

@media (max-width: 480px) {
  .auth-card {
    width: 90%;
    padding: 30px 20px;
  }
}
</style>