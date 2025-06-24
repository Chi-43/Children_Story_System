<template>
  <div class="home-container">
    <el-container>
      <!-- 侧边栏 - 保持原有功能不变 -->
      <el-aside width="250px" class="sidebar">
        <div class="user-info">
          <el-avatar :size="50" :src="userAvatar" />
          <span class="username">{{ authStore.user?.username }}</span>
          <el-button type="text" @click="authStore.logout" class="logout-btn">
            退出登录
          </el-button>
        </div>

        <el-button type="primary" @click="newConversation" class="new-chat-btn">
          <el-icon><plus /></el-icon>
          新对话
        </el-button>

        <el-menu :default-active="activeConversation" class="conversation-list">
          <el-menu-item
            v-for="(conv, index) in conversations"
            :key="index"
            :index="String(index)"
            @click="selectConversation(index)"
          >
            <span>{{ conv.title }}</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 - 修改为故事风格 -->
      <el-main class="story-container">
        <div class="story-welcome">
          <h2>儿童故事乐园</h2>
          <p>
            <strong
              >你好！我是故事精灵，可以为你创作有趣的人类故事并进行情感分析。你想听什么故事呢？</strong
            >
          </p>
        </div>

        <!-- 保留原有的消息列表，但初始隐藏 -->
        <div
          class="message-list"
          ref="messageList"
          v-show="currentMessages.length > 0"
        >
          <div
            v-for="(msg, index) in currentMessages"
            :key="index"
            :class="['message-item', msg.role]"
          >
            <div class="message-content">
              <div class="message-avatar">
                <el-avatar
                  :size="40"
                  :src="msg.role === 'user' ? userAvatar : botAvatar"
                />
              </div>
              <div class="message-text">
                <div class="message-meta">
                  <span class="message-role">{{
                    msg.role === "user" ? "你" : "AI助手"
                  }}</span>
                  <span class="message-time">{{ msg.timestamp }}</span>
                  <el-button
                    v-if="msg.role === 'ai' && msg.content.length > 10"
                    size="small"
                    @click="analyzeSentiment(msg.content)"
                    class="sentiment-btn"
                  >
                    情感分析
                  </el-button>
                </div>
                <div class="message-body">{{ msg.content }}</div>
                <div v-if="msg.sentiment" class="sentiment-result">
                  <el-tag :type="getSentimentTagType(msg.sentiment.label)">
                    {{ getSentimentLabel(msg.sentiment.label) }}
                    ({{ (msg.sentiment.score * 100).toFixed(1) }}%)
                  </el-tag>
                  <p v-if="msg.sentiment.recommendation" class="recommendation">
                    {{ msg.sentiment.recommendation }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 故事生成表单 -->
        <div class="input-area">
          <el-form :model="storyForm" label-width="80px">
            <el-form-item label="儿童年龄">
              <el-input-number v-model="storyForm.age" :min="3" :max="12" />
            </el-form-item>
            <el-form-item label="故事主题">
              <el-input
                v-model="storyForm.theme"
                placeholder="如：勇敢、友谊等"
              />
            </el-form-item>
            <el-form-item label="特殊要求">
              <el-input
                v-model="storyForm.requirements"
                type="textarea"
                placeholder="如：主角是小狗、要有魔法元素等"
              />
            </el-form-item>
            <el-form-item label="故事长度">
              <el-select v-model="storyForm.length" placeholder="请选择">
                <el-option label="短篇(约200字)" value="200" />
                <el-option label="中篇(约500字)" value="500" />
                <el-option label="长篇(约1000字)" value="1000" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                @click="generateStory"
                :loading="isSending"
                class="send-btn"
              >
                生成故事
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 热门主题推荐 -->
          <div class="popular-themes">
            <h4>热门故事主题：</h4>
            <ul>
              <li @click="setTheme('勇敢的小兔子')">
                <strong>勇敢的小兔子</strong>
              </li>
              <li @click="setTheme('友谊的力量')">
                <strong>友谊的力量</strong>
              </li>
              <li @click="setTheme('森林冒险')">
                <strong>森林冒险</strong>
              </li>
              <li @click="setTheme('超级英雄')">
                <strong>超级英雄</strong>
              </li>
            </ul>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
// 保持原有的script部分完全不变
import { ref, computed, onMounted, nextTick } from "vue";
import { useAuthStore } from "../stores/auth";
import { Plus } from "@element-plus/icons-vue";
import axios from "axios";
import { ElMessage } from "element-plus";

const authStore = useAuthStore();

const storyForm = ref({
  age: 6,
  theme: "",
  requirements: "",
  length: "500",
});

const isSending = ref(false);
const conversations = ref([]);
const currentMessages = ref([]);
const activeConversation = ref(0);
const messageList = ref(null);
const isAnalyzing = ref(false);

const userAvatar = computed(
  () =>
    `https://api.dicebear.com/7.x/initials/svg?seed=${authStore.user?.username}`
);
const botAvatar = "https://api.dicebear.com/7.x/bottts/svg?seed=AI";

// 初始化对话
const initConversations = () => {
  const saved = localStorage.getItem(`conversations_${authStore.user?.id}`);
  if (saved) {
    conversations.value = JSON.parse(saved);
    if (conversations.value.length > 0) {
      currentMessages.value = conversations.value[0].messages || [];
    }
  } else {
    newConversation();
  }
};

// 创建新对话
const newConversation = () => {
  const newConv = {
    title: `新对话 ${conversations.value.length + 1}`,
    messages: [],
    createdAt: new Date().toLocaleString(),
  };
  conversations.value.unshift(newConv);
  activeConversation.value = 0;
  currentMessages.value = [];
  saveConversations();
};

// 选择对话
const selectConversation = (index) => {
  activeConversation.value = index;
  currentMessages.value = conversations.value[index].messages;
};

// 设置主题
const setTheme = (theme) => {
  storyForm.value.theme = theme;
};

  // 生成故事
  const generateStory = async () => {
    if (!storyForm.value.theme.trim()) {
      ElMessage.warning("请输入故事主题");
      return;
    }

    const userMsg = {
      role: "user",
      content: `请求生成故事：
      年龄: ${storyForm.value.age}岁
      主题: ${storyForm.value.theme}
      要求: ${storyForm.value.requirements}
      长度: ${storyForm.value.length}字`,
      timestamp: new Date().toLocaleTimeString(),
    };

    currentMessages.value.push(userMsg);
    saveConversations();
    scrollToBottom();

    try {
      isSending.value = true;
      
      // 创建AI消息占位
      const aiMsg = {
        role: "ai",
        content: "",
        timestamp: new Date().toLocaleTimeString(),
      };
      currentMessages.value.push(aiMsg);
      saveConversations();
      
      // 使用fetch API实现SSE (POST方法)
      const response = await fetch(
        "http://localhost:5000/api/generate_story",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authStore.token}`,
          },
          body: JSON.stringify({
            age: storyForm.value.age,
            theme: storyForm.value.theme,
            requirements: storyForm.value.requirements,
            length: storyForm.value.length,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          isSending.value = false;
          break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data:')) {
            const data = JSON.parse(line.substring(5).trim());
            if (data.text) {
              aiMsg.content += data.text;
              currentMessages.value = [...currentMessages.value];
              saveConversations();
              scrollToBottom();
            }
          }
        }
      }
    } catch (error) {
      ElMessage.error("生成故事失败: " + error.message);
      isSending.value = false;
    }
  };

// 情感分析
const analyzeSentiment = async (text) => {
  try {
    isAnalyzing.value = true;
    const response = await axios.post(
      "http://localhost:5000/api/analyze_sentiment",
      { text },
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`,
        },
      }
    );

    const sentiment = response.data;
    sentiment.recommendation = getRecommendation(sentiment.label);

    // 更新当前消息的情感分析结果
    const msgIndex = currentMessages.value.findIndex(
      (msg) => msg.content === text
    );
    if (msgIndex !== -1) {
      currentMessages.value[msgIndex].sentiment = sentiment;
      saveConversations();
    }
  } catch (error) {
    ElMessage.error("情感分析失败: " + error.message);
  } finally {
    isAnalyzing.value = false;
  }
};

// 获取情感标签显示文本
const getSentimentLabel = (label) => {
  const labels = {
    LABEL_0: "负面",
    LABEL_1: "中性",
    LABEL_2: "正面",
  };
  return labels[label] || label;
};

// 获取情感标签类型
const getSentimentTagType = (label) => {
  const types = {
    LABEL_0: "danger",
    LABEL_1: "info",
    LABEL_2: "success",
  };
  return types[label] || "";
};

// 获取推荐内容
const getRecommendation = (label) => {
  const recommendations = {
    LABEL_0: "检测到负面情绪，推荐阅读积极向上的故事",
    LABEL_1: "故事情感中性，可以尝试更有趣的主题",
    LABEL_2: "故事情感积极，继续保持哦！",
  };
  return recommendations[label] || "";
};

// 保存对话
const saveConversations = () => {
  conversations.value[activeConversation.value].messages =
    currentMessages.value;
  localStorage.setItem(
    `conversations_${authStore.user?.id}`,
    JSON.stringify(conversations.value)
  );
};

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messageList.value) {
      messageList.value.scrollTop = messageList.value.scrollHeight;
    }
  });
};

onMounted(() => {
  initConversations();
});
</script>

<style scoped>
.home-container {
  height: 100vh;
  display: flex;
  background-color: #f9f9f9;
}

.sidebar {
  background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
  color: white;
  height: 100vh;
  padding: 20px;
  position: relative;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 10px;
}

.username {
  margin: 10px 0;
  font-weight: bold;
  color: white;
}

.logout-btn {
  color: white;
  opacity: 0.8;
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 20px;
  background: white;
  color: #6c5ce7;
  border: none;
  font-weight: bold;
}

.conversation-list {
  border-right: none;
  background: transparent;
}

.conversation-list :deep(.el-menu-item) {
  color: white;
  margin-bottom: 5px;
  border-radius: 8px;
}

.conversation-list :deep(.el-menu-item.is-active) {
  background-color: rgba(255, 255, 255, 0.3);
}

/* 新的故事风格样式 */
.story-container {
  padding: 30px;
  background-color: white;
  height: 100vh;
  overflow-y: auto;
  background-image: url("https://img.freepik.com/free-vector/hand-painted-watercolor-pastel-sky-background_23-2148902771.jpg");
  background-size: cover;
  background-position: center;
}

.story-header {
  text-align: center;
  margin-bottom: 40px;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 15px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.story-header h1 {
  color: #6c5ce7;
  font-size: 2.5rem;
  margin-bottom: 15px;
  font-family: "Comic Sans MS", cursive, sans-serif;
}

.story-categories h2,
.story-categories h3 {
  color: #333;
  margin: 5px 0;
}

.story-categories h2 {
  font-size: 1.8rem;
  color: #e84393;
}

.story-categories h3 {
  font-size: 1.4rem;
  color: #0984e3;
}

.story-welcome {
  background-color: rgba(255, 255, 255, 0.85);
  padding: 30px;
  border-radius: 15px;
  margin-bottom: 30px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.story-welcome h2 {
  color: #6c5ce7;
  font-size: 2rem;
  margin-bottom: 15px;
  text-align: center;
}

.story-welcome p {
  font-size: 1.1rem;
  line-height: 1.6;
  color: #333;
  margin-bottom: 15px;
}

.popular-themes {
  margin-top: 15px;
}

.popular-themes h4 {
  font-size: 1rem;
  color: #6c5ce7;
  margin-bottom: 8px;
}

.popular-themes ul {
  list-style-type: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.popular-themes li {
  font-size: 0.9rem;
  padding: 4px 10px;
  margin: 0;
  background-color: rgba(108, 92, 231, 0.1);
  border-radius: 6px;
  color: #6c5ce7;
  cursor: pointer;
  transition: all 0.2s;
}

.popular-themes li:hover {
  background-color: rgba(108, 92, 231, 0.2);
  transform: translateY(-2px);
}

/* 保留原有的消息样式 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 15px;
  margin-bottom: 20px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.message-item {
  margin-bottom: 20px;
}

.message-content {
  display: flex;
  max-width: 80%;
  margin: 0 auto;
}

.user .message-content {
  flex-direction: row-reverse;
}

.message-avatar {
  margin: 0 15px;
}

.message-text {
  flex: 1;
}

.message-meta {
  font-size: 12px;
  color: #666;
  margin-bottom: 5px;
}

.message-body {
  background: white;
  padding: 12px 18px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  white-space: pre-line;
}

.sentiment-btn {
  margin-left: 10px;
  background: linear-gradient(135deg, #ff7675 0%, #fdcb6e 100%);
  color: white;
  border: none;
}

.sentiment-result {
  margin-top: 10px;
  padding: 10px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
}

.sentiment-result .el-tag {
  margin-right: 10px;
}

.recommendation {
  margin: 5px 0 0;
  font-size: 0.9em;
  color: #666;
}

.user .message-body {
  background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
  color: white;
}

.input-area {
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 15px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.send-btn {
  margin-top: 10px;
  background: linear-gradient(135deg, #00b894 0%, #55efc4 100%);
  color: white;
  border: none;
}
</style>
