const { createApp, ref, onMounted } = Vue;

createApp({
    setup() {
        const userInput = ref('');
        const conversations = ref([]);
        const currentConversation = ref(0);
        const currentMessages = ref([]);
        const currentUser = ref(null);
        const showLoginModal = ref(false);
        const isLogin = ref(true);
        const authForm = ref({
            username: '',
            password: ''
        });
        const apiBaseUrl = 'http://localhost:5000';
        const authToken = ref('');

        // 用户认证处理
        const handleAuth = async () => {
            const url = isLogin.value ? `${apiBaseUrl}/api/login` : `${apiBaseUrl}/api/register`;
            
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: authForm.value.username,
                        password: authForm.value.password
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    authToken.value = data.token;
                    currentUser.value = {
                        id: data.user_id,
                        username: authForm.value.username
                    };
                    showLoginModal.value = false;
                    loadUserConversations();
                } else {
                    alert(data.error || '认证失败');
                }
            } catch (error) {
                alert('网络错误，请稍后重试');
            }
        };

        // 退出登录
        const logout = () => {
            currentUser.value = null;
            conversations.value = [];
            currentMessages.value = [];
        };

        // 加载用户对话
        const loadUserConversations = () => {
            const userConversations = JSON.parse(
                localStorage.getItem(`ai-chat-conversations-${currentUser.value.id}`) || '[]'
            );
            conversations.value = userConversations;
            if (conversations.value.length > 0) {
                currentMessages.value = conversations.value[0].messages || [];
            } else {
                newConversation();
            }
        };

        // 初始化或从本地存储加载对话
        onMounted(() => {
            const saved = localStorage.getItem('ai-chat-conversations');
            if (saved) {
                conversations.value = JSON.parse(saved);
                if (conversations.value.length > 0) {
                    currentMessages.value = conversations.value[0].messages || [];
                }
            } else {
                newConversation();
            }
        });

        // 创建新对话
        const newConversation = () => {
            const newConv = {
                title: '新对话 ' + (conversations.value.length + 1),
                messages: [],
                createdAt: new Date().toLocaleString()
            };
            conversations.value.unshift(newConv);
            currentConversation.value = 0;
            currentMessages.value = [];
            saveConversations();
        };

        // 加载对话
        const loadConversation = (index) => {
            currentConversation.value = index;
            currentMessages.value = conversations.value[index].messages;
        };

        // 发送消息
        const sendMessage = async () => {
            if (!userInput.value.trim() || !currentUser.value) {
                alert('请先登录并输入消息');
                return;
            }

            const userMsg = {
                role: 'user',
                content: userInput.value,
                timestamp: new Date().toLocaleTimeString()
            };

            // 添加到当前对话
            currentMessages.value.push(userMsg);
            conversations.value[currentConversation.value].messages = currentMessages.value;
            saveConversations();

            try {
                console.log('发送请求到后端:', {
                    url: `${apiBaseUrl}/api/ask`,
                    token: authToken.value,
                    question: userInput.value
                });

                const response = await fetch(`${apiBaseUrl}/api/ask`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken.value}`
                    },
                    body: JSON.stringify({
                        question: userInput.value
                    })
                });

                console.log('收到响应:', response);

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `请求失败: ${response.status}`);
                }

                const data = await response.json();
                console.log('API响应数据:', data);

                const aiMsg = {
                    role: 'ai',
                    content: data.answer,
                    timestamp: new Date().toLocaleTimeString()
                };
                currentMessages.value.push(aiMsg);
                saveConversations();
            } catch (error) {
                console.error('发送消息出错:', error);
                const errorMsg = {
                    role: 'ai',
                    content: `错误: ${error.message}`,
                    timestamp: new Date().toLocaleTimeString()
                };
                currentMessages.value.push(errorMsg);
                alert(`发送消息失败: ${error.message}`);
            } finally {
                userInput.value = '';
                saveConversations();
            }
        };

        // 保存对话到本地存储
        const saveConversations = () => {
            if (currentUser.value) {
                localStorage.setItem(
                    `ai-chat-conversations-${currentUser.value.id}`,
                    JSON.stringify(conversations.value)
                );
            } else {
                localStorage.setItem(
                    'ai-chat-conversations',
                    JSON.stringify(conversations.value)
                );
            }
        };

        return {
            userInput,
            conversations,
            currentConversation,
            currentMessages,
            currentUser,
            showLoginModal,
            isLogin,
            authForm,
            newConversation,
            loadConversation,
            sendMessage,
            handleAuth,
            logout
        };
    }
}).mount('#app');
