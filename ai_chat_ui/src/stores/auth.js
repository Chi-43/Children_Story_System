import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token'))
  const user = ref(JSON.parse(localStorage.getItem('user') || null))
  const isAuthenticated = ref(false)

  const apiBaseUrl = 'http://localhost:5000'

  const login = async (username, password) => {
    try {
      const response = await axios.post(`${apiBaseUrl}/api/login`, {
        username,
        password
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      token.value = response.data.token
      user.value = { id: response.data.user_id, username }
      isAuthenticated.value = true
      
      localStorage.setItem('token', token.value)
      localStorage.setItem('user', JSON.stringify(user.value))
      
      router.push('/')
      return true
    } catch (error) {
      console.error('Login failed:', error)
      throw error // 抛出错误让调用方处理
    }
  }

  const register = async (username, password) => {
    try {
      const response = await axios.post(`${apiBaseUrl}/api/register`, {
        username,
        password
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      token.value = response.data.token
      user.value = { id: response.data.user_id, username }
      isAuthenticated.value = true
      
      localStorage.setItem('token', token.value)
      localStorage.setItem('user', JSON.stringify(user.value))
      
      router.push('/')
      return true
    } catch (error) {
      console.error('Registration failed:', error)
      throw error // 抛出错误让调用方处理
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    isAuthenticated.value = false
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    logout
  }
})
