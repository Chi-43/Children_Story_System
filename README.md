# -
儿童故事生成与情感分析系统设计与实现​
kids_story_ai/
├── app.py                            # Flask 应用入口
├── config.py                         # 配置文件（API Key、模型设置）
├── requirements.txt                  # Python 依赖
│
├── templates/                        # 前端模板（Flask 渲染页面）
│   └── index.html                    # 故事生成主页面
│
├── static/                           # JS、CSS 静态资源
│   ├── main.js
│   └── style.css
│
├── langchain_modules/                # LangChain 封装模块
│   ├── loader.py                     # 文档加载与切割：构建素材库
│   ├── story_generator.py            # 故事生成逻辑（提示词 + LLM）
│   ├── sentiment_analysis.py         # 情感分析模块
│   └── content_filter.py             # 年龄过滤与敏感词排查
│
├── data/                             # 存储原始素材库（txt等）
│   ├── fairy_tales/
│   ├── modern_stories/
│   └── folk_legends/
│
├── uploads/                          # 用户上传的音频/文本等交互数据（用于分析）
│
├── logs/                             # 日志文件、情感记录（可选）
│
└── README.md                         # 项目说明
