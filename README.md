# AI代码生成与RAG流水线工具

一个基于 **Python + PyQt5 + LLM + RAG** 的智能代码生成与任务流水线工具。

该项目提供一个 **图形化界面 (GUI)**，支持：

- 🤖 LLM代码生成
- 📚 RAG知识库检索 (ChromaDB)
- 🧠 智能问答
- 🔁 批量任务流水线
- 📊 变量表测试
- 📝 Word报告自动生成

项目采用 **前后端分离架构**，便于扩展和维护。

---

# 项目架构

项目代码结构如下：


src_py/
├── main.py # 程序入口
├── config.py # 配置文件
│
├── backend/ # 后端逻辑（纯Python，无GUI依赖）
│ ├── api_client.py # LLM API调用封装
│ ├── prompt_builder.py # Prompt构建模块
│ ├── rag_core.py # RAG + ChromaDB检索
│ ├── code_parser.py # 代码提取与需求解析
│ ├── pipeline_engine.py # 批量任务流水线引擎
│ └── report_generator.py # Word报告生成
│
└── ui/ # PyQt5 前端界面
├── workers.py # QThread线程封装
├── widgets.py # UI组件
├── main_window.py # 主窗口
├── tab_generation.py # 代码生成Tab
├── tab_kb.py # 知识库管理Tab
├── tab_settings.py # 设置Tab
├── tab_qa.py # 问答Tab
├── tab_pipeline.py # 流水线Tab
└── tab_var_test.py # 变量测试Tab


---

# 核心设计思想

## 前后端分离

项目将 **GUI界面和核心逻辑彻底分离**：

| 目录 | 作用 |
|-----|-----|
| backend | 纯Python逻辑模块 |
| ui | PyQt5界面 |
| main.py | 程序入口 |

这样带来的好处：

- backend 可独立测试
- 未来可接入 Web UI（FastAPI / Flask）
- GUI不会污染核心逻辑

---

## Prompt逻辑集中管理

所有Prompt构建统一在：


backend/prompt_builder.py


提供四类Prompt：

| 方法 | 作用 |
|----|----|
| build_generation_prompt | 单次代码生成 |
| build_pipeline_prompt | 批量代码生成 |
| build_qa_prompt | 智能问答 |
| build_variable_test_prompt | 变量测试 |

这样避免Prompt分散在多个文件中。

---

# 功能模块

## 1 代码生成

基于LLM生成代码，支持结构化输出。

---

## 2 RAG知识库检索

通过 **ChromaDB向量数据库**实现：

- 文档向量化
- 语义检索
- 上下文增强生成

---

## 3 知识库管理

支持：

- 文档导入
- 向量化存储
- 知识检索

---

## 4 批量流水线任务

通过流水线系统支持：

- 批量任务解析
- 变量表替换
- 多文件代码生成

---

## 5 变量测试

用于验证变量表是否正确解析。

---

## 6 Word报告生成

自动生成：


需求分析报告
代码生成报告
测试报告


基于 **Word模板替换实现**。

---

# 安装说明

## Python版本

推荐：


Python 3.9+


---

## 安装依赖

如果有 `requirements.txt`：


pip install -r requirements.txt


常见依赖包括：


PyQt5
chromadb
requests
python-docx


---

# 运行项目

在项目根目录执行：


python src_py/main.py


程序将启动 PyQt5 图形界面。

---

# Git开发流程

推荐使用 **develop + main 分支模型**：


develop -> 日常开发
main -> 稳定版本


开发流程：


develop 开发
↓
测试功能
↓
merge到 main
↓
发布版本


示例：


git checkout develop
git commit -m "新增功能"

git checkout main
git merge develop
git push origin main

git tag -a v2.0 -m "Release v2.0"
git push origin v2.0


---

# 项目未来计划

未来可能增加：

- Web UI版本（FastAPI）
- Prompt版本管理
- 多模型评测系统
- 插件式流水线模块

---

# 作者

**Zhendong Sun**

---

# 说明

本项目用于：

- AI代码生成研究
- RAG系统实验
- 自动化代码生成流程探索
如何使用

1️⃣ 在项目根目录创建文件

README.md

2️⃣ 把上面内容粘进去

3️⃣ 提交到仓库

git add README.md
git commit -m "add README"
git push origin main