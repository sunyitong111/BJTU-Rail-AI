import streamlit as st
import os
import subprocess
import time
from openai import OpenAI
from fitz import open as open_pdf
from pptx import Presentation

# --- 1. 系统核心配置 (LLM Engine) ---
# 建议：提交报告时，API Key 中间部分可打码
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# --- 2. 页面全局配置与专业 UI 定制 ---
st.set_page_config(
    page_title="BJTU 轨道交通AI助理",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS 样式：强化北交大品牌视觉感
st.markdown("""
    <style>
    .header-style {
        background-color: #004294; 
        padding: 25px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .author-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 6px solid #004294;
        margin-bottom: 20px;
        font-size: 0.9em;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        transition: all 0.3s;
    }
    .footer {
        position: fixed;
        left: 0; bottom: 0; width: 100%;
        background-color: rgba(255,255,255,0.9);
        text-align: center; padding: 10px; font-size: 12px;
        color: #666; border-top: 1px solid #eee; z-index: 100;
    }
    </style>
    """, unsafe_allow_html=True)


# --- 3. 知识库构建模块 (RAG Module) ---

@st.cache_data(show_spinner=False)
def get_local_context_with_sources(folder_path="."):
    """
    核心算法：实现多格式课件的语义提取与编码容错
    """
    context_list, source_names = [], []
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    valid_extensions = ('.md', '.txt', '.pdf', '.pptx')
    files = [f for f in os.listdir(folder_path) if f.endswith(valid_extensions)]

    for file in files:
        path = os.path.join(folder_path, file)
        text = ""
        try:
            # 1. 处理文本类文件（增加编码自动切换机制）
            if file.endswith(('.md', '.txt')):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        text = f.read()
                except UnicodeDecodeError:
                    with open(path, 'r', encoding='gbk') as f:
                        text = f.read()

            # 2. 处理 PDF 类文件（学术课件核心）
            elif file.endswith(".pdf"):
                with open_pdf(path) as doc:
                    text = "".join([page.get_text() for page in doc])

            # 3. 处理 PPTX 类文件（教学讲义核心）
            elif file.endswith(".pptx"):
                prs = Presentation(path)
                text = " ".join([shape.text for slide in prs.slides
                                 for shape in slide.shapes if hasattr(shape, "text")])

            if text.strip():
                # 优化：提升上下文注入长度至 8000 字符，适应长文档
                context_list.append(text[:8000])
                source_names.append(file)
        except Exception as e:
            print(f"解析文件 {file} 时出错: {str(e)}")
            continue
    return context_list, source_names


# --- 4. Agent 决策推理核心 ---

def ask_ai(user_query):
    with st.status("Agent 正在处理请求...", expanded=False) as status:
        st.write("🔍 正在检索本地轨道交通专业知识库...")
        contexts, sources = get_local_context_with_sources()

        if not sources:
            combined_context = "（当前本地知识库为空，请基于通用专业知识回答）"
            source_info = "互联网专业数据库"
        else:
            combined_context = "\n\n".join([f"内容来源【{s}】：\n{c}" for s, c in zip(sources, contexts)])
            source_info = "、".join(sources)

        st.write("🧠 正在进行语义对齐与逻辑推理...")

        # 提示词工程：规范 Agent 的学术行为
        system_prompt = f"""你是一个轨道交通移动通信专家教学助理。
        你的任务是基于提供的本地课件内容以及你自身的互联网专业知识回答用户问题。

        【回答准则】：
        1. 每一篇回答的开头必须固定为：**“根据本地知识库和网上资料，为您查询到如下内容：”**
        2. 引用优先：如果【参考知识库内容】中有相关信息，必须优先提取并解读。
        3. 溯源标注：必须在回答结尾以『📚 参考资料：文件名』形式精准标注。
        4. 学术表达：数学公式必须使用标准 LaTeX 渲染（例如 $f_d = \\frac{{v}}{{c}} f_c$）。

        【参考知识库内容】：
        {combined_context}
        """

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.3  # 保证学术回答的稳定性
            )
            status.update(label="✅ 处理完成", state="complete", expanded=False)
            return response.choices[0].message.content
        except Exception as e:
            status.update(label="❌ 引擎故障", state="error")
            return f"⚠️ 接口调用失败: {str(e)}"


# --- 5. 跨平台工具调用 (Tool Use) ---

def run_matlab_sim():
    # 增加环境检查
    if os.name != 'nt': # Streamlit Cloud 通常是 Linux，你的电脑是 Windows(nt)
        st.warning("⚠️ 仿真功能仅支持在本地 Windows 环境运行（需要安装 MATLAB）。")
        return False
    try:
        cmd = "matlab -nosplash -nodesktop -r \"run('channel_sim');\""
        subprocess.Popen(cmd, shell=True)
        st.toast("🚀 MATLAB 仿真环境启动中...", icon="⚡")
        return True
    except Exception as e:
        st.error(f"无法启动 MATLAB: {e}")
        return False

# --- 6. 侧边栏交互组件 ---

with st.sidebar:
    st.markdown("### 🏫 北京交通大学")
    st.markdown(f"""
        <div class="author-card">
            <b>制作者：</b>孙涛<br>
            <b>学号：</b>23211436<br>
            <b>课程：</b>轨道交通移动通信系统
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("🛠️ 实验工具箱")
    if st.button("🚀 启动 MATLAB 仿真实验"):
        run_matlab_sim()

    st.divider()
    st.subheader("📚 知识库管理 (RAG)")
    if os.path.exists("."):
        files = os.listdir(".")
        if files:
            for f in files:
                if f.endswith('.pdf'):
                    st.caption(f"📕 {f}")
                elif f.endswith('.pptx'):
                    st.caption(f"📊 {f}")
                elif f.endswith(('.md', '.txt')):
                    st.caption(f"📝 {f}")
        else:
            st.warning("知识库文件夹为空")

    if st.button("🔄 刷新并重载知识库"):
        st.cache_data.clear()
        st.success("缓存已清空，正在重载...")
        time.sleep(1)
        st.rerun()

# --- 7. 主界面逻辑 ---

st.markdown('<div class="header-style"><h1>轨道交通移动通信系统 AI 教学助理</h1></div>', unsafe_allow_html=True)

# 快捷指令模块：引导学生提问
st.write("💡 **专业指令快捷键：**")
col1, col2, col3 = st.columns(3)
quick_query = None
with col1:
    if st.button("🚄 绪论：系统演进分析"):
        quick_query = "请详细介绍第一章绪论中关于轨道交通移动通信的发展历程。"
with col2:
    if st.button("📡 5G-R 关键技术对比"):
        quick_query = "5G-R 相比 GSM-R 有哪些核心技术改进？请对比带宽与时延。"
with col3:
    if st.button("📐 计算多普勒频移"):
        quick_query = "给定列车速度350km/h，载波频率2.1GHz，请展示多普勒频移的计算过程。"

# 渲染对话历史
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 交互输入逻辑
prompt = st.chat_input("请输入您的问题（例如：解释越区切换流程）...")
final_input = quick_query if quick_query else prompt

if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    with st.chat_message("assistant"):
        answer = ask_ai(final_input)
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

# 页脚
st.markdown('<div class="footer">© 2026 北京交通大学 · 通信工程专业 · 孙涛 (23211436)</div>', unsafe_allow_html=True)
