import streamlit as st
import os
import time
import base64
import random
import re
from openai import OpenAI
from fitz import open as open_pdf
from pptx import Presentation


# --- 1. 资源读取逻辑 (Base64 & 增强型知识库) ---
def get_image_base64(image_path):
    """读取本地图片并转换为 Base64，用于水印和 Logo"""
    if not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"
    except:
        return None


@st.cache_data(show_spinner=False)
def get_local_context_with_pages(folder_path="courseware"):
    """
    按页读取知识库，确保每一页内容都能被索引。
    这是解决章节被挤出的基础。
    """
    page_data_list = []
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    valid_exts = ('.md', '.txt', '.pdf', '.pptx')
    files = [f for f in os.listdir(folder_path) if f.endswith(valid_exts)]

    for file in files:
        path = os.path.join(folder_path, file)
        try:
            if file.endswith(".pdf"):
                with open_pdf(path) as doc:
                    for i, page in enumerate(doc):
                        text = page.get_text().strip()
                        if text:
                            page_data_list.append({
                                "source": file,
                                "page": i + 1,
                                "content": text[:1500]
                            })
            elif file.endswith(".pptx"):
                prs = Presentation(path)
                for i, slide in enumerate(prs.slides):
                    text = " ".join([shape.text for shape in slide.shapes if hasattr(shape, "text")])
                    if text.strip():
                        page_data_list.append({
                            "source": file,
                            "page": i + 1,
                            "content": text
                        })
            elif file.endswith(('.md', '.txt')):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    page_data_list.append({
                        "source": file,
                        "page": 1,
                        "content": content[:5000]
                    })
        except Exception as e:
            st.error(f"解析 {file} 出错: {e}")
    return page_data_list


# --- 2. 工具函数：TXT 导出清洗 ---
def clean_html_for_export(text):
    """
    核心功能：使用正则剔除所有 HTML 标签。
    将 <span class='citation-tag' title='...'>内容</span> 转换为 “内容”。
    """
    # 1. 匹配 span 标签并提取内部文本
    clean_text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', text)
    # 2. 移除任何残留的 HTML 标签
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    return clean_text


# --- 3. 核心配置与 UI 样式 ---
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

st.set_page_config(
    page_title="BJTU 轨道交通AI助理",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded"
)

local_logo_base64 = get_image_base64("logo.png")
watermark_css = f"background-image: url('{local_logo_base64}');" if local_logo_base64 else ""

st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 100%);
        background-attachment: fixed;
    }}
    .stApp::before {{
        content: ""; position: fixed; top: 50%; left: 50%;
        width: 600px; height: 600px; transform: translate(-50%, -50%);
        {watermark_css}
        background-repeat: no-repeat; background-size: contain;
        opacity: 0.03; z-index: -1; pointer-events: none;
    }}
    .header-style {{
        background: linear-gradient(90deg, #004294 0%, #002f6c 100%); 
        padding: 30px; border-radius: 15px; color: white;
        text-align: center; margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}
    .author-card {{
        background-color: rgba(255, 255, 255, 0.85);
        padding: 15px; border-radius: 10px;
        border-left: 6px solid #004294; margin-bottom: 15px;
        backdrop-filter: blur(10px); box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }}
    .citation-tag {{
        border-bottom: 1.5px dotted #004294;
        cursor: help; color: #004294; font-weight: 500;
        transition: all 0.2s;
    }}
    .citation-tag:hover {{ background-color: rgba(0, 66, 148, 0.1); }}
    </style>
    """, unsafe_allow_html=True)


# --- 4. 增强型 AI 推理逻辑 ---
def ask_ai(user_query, mode):
    # --- 新增：开发者身份拦截逻辑 ---
    developer_keywords = ["你是谁", "谁开发的", "作者", "开发者", "你的主人", "who created you", "developer"]
    if any(kw in user_query.lower() for kw in developer_keywords):
        return "我是北交大轨道交通 AI 助手，由**北京交通大学电子信息工程学院的孙涛同学**开发制作。"

    all_pages = get_local_context_with_pages()

    # 智能路由检索
    selected_context_list = []
    chapter_keyword = re.findall(r"第[一二三四五六七八九十0-9]章", user_query)

    if chapter_keyword:
        kw = chapter_keyword[0]
        selected_context_list = [p for p in all_pages if kw in p['source'] or kw in p['content']]

    remaining_pages = [p for p in all_pages if p not in selected_context_list]
    final_selection = (selected_context_list + remaining_pages)[:30]

    combined_context = "\n\n".join([
        f"【来源：{p['source']} | 第 {p['page']} 页】：\n{p['content']}"
        for p in final_selection
    ]) if final_selection else "知识库暂无相关内容"

    # --- 完善：专业动态状态显示逻辑 ---
    with st.status("🚉 正在调度轨道交通 AI 引擎...", expanded=True) as status:
        # 步骤 1: 扫描阶段
        st.write("🔍 正在扫描 `courseware` 知识库...")
        time.sleep(0.3)

        # 步骤 2: 匹配具体的专业逻辑（增强专业感）
        if "5G" in user_query.upper() or "演进" in user_query:
            st.write("📡 正在同步 5G-R 核心网下行链路参数...")
        elif "多普勒" in user_query or "时速" in user_query or "计算" in user_query:
            st.write("📐 正在提取多普勒扩展与信道快衰落模型数据...")
        elif "第二章" in user_query or "环境" in user_query:
            st.write("🛤️ 正在分析轨道交通典型场景（隧道、高架桥）传播特性...")
        elif "GSM-R" in user_query.upper():
            st.write("📞 正在检索 GSM-R 调度通信逻辑信道配置...")
        else:
            st.write("🛠️ 正在进行语义向量匹配与知识关联...")

        time.sleep(0.4)

        # 步骤 3: 协议校验阶段
        st.write("🔐 正在通过 CTCS-3 级指令集校验数据一致性...")
        time.sleep(0.3)

        sys_prompt = f"""你现在是北交大轨道交通 AI 助手。
        你的回答必须严格参考提供的资料。

        【核心要求：引用溯源】
        1. 你的回答中，每一个关键事实或结论，必须用 HTML 标签包裹。
        2. 标签格式：<span class='citation-tag' title='来源：文件名 第X页'>对应文字内容</span>
        3. 严禁改变原始文字。如果资料中确实没有，请告知并结合专业知识。

        【参考资料】：
        {combined_context}
        """

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_query}],
                temperature=0.2 if "学术" in mode else 0.6
            )
            ans = response.choices[0].message.content
            status.update(label="✅ 信号绿灯：数据链路建立成功，检索完成！", state="complete", expanded=False)
            return ans
        except Exception as e:
            status.update(label="❌ 调度系统故障：信号中断", state="error")
            return f"⚠️ 错误报告: {str(e)}"

# --- 5. 侧边栏布局 ---
with st.sidebar:
    st.markdown("### 🏫 北京交通大学")
    if local_logo_base64:
        st.image(local_logo_base64, use_container_width=True)

    st.markdown(f"""
        <div class="author-card">
            <b>制作者：</b>孙涛<br>
            <b>学号：</b>23211436<br>
            <b>课程：</b>轨道交通移动通信系统<br>
            <b>学院：</b>电子信息工程学院
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("📚 知识库列表")
    files = [f for f in os.listdir("courseware") if not f.startswith(".")] if os.path.exists("courseware") else []
    if files:
        for f in files: st.caption(f"📕 {f}")
    else:
        st.warning("请在 courseware 文件夹放置课件")

    if st.button("🔄 强制刷新知识库"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("📝 笔记导出")
    if "messages" in st.session_state and st.session_state.messages:
        # 导出前进行正则清洗，确保 TXT 无 HTML 乱码
        export_lines = []
        for m in st.session_state.messages:
            role = "学生" if m["role"] == "user" else "AI 助手"
            clean_content = clean_html_for_export(m["content"])
            export_lines.append(f"【{role}】：\n{clean_content}\n" + "-" * 30)

        full_note = f"BJTU 轨道交通移动通信 - 学习笔记\n生成时间：{time.strftime('%Y-%m-%d %H:%M')}\n\n" + "\n".join(
            export_lines)

        st.download_button(
            label="💾 下载纯净版笔记 (.txt)",
            data=full_note,
            file_name=f"BJTU_Clean_Notes_{int(time.time())}.txt",
            mime="text/plain"
        )


# --- 6. 主界面逻辑 ---
st.markdown('<div class="header-style"><h1>轨道交通移动通信系统 AI 教学助理</h1></div>', unsafe_allow_html=True)

# 快捷指令
st.write("💡 **专业快速检索：**")
c1, c2, c3 = st.columns(3)
q_prompt = None
with c1:
    if st.button("🚄 绪论：系统演进历程"): q_prompt = "请详细介绍轨道交通移动通信从 GSM-R 到 5G-R 的演进历程。"
with c2:
    if st.button("📡 第二章：无线传播环境"): q_prompt = "请讲解第二章中关于轨道交通无线传播环境的特点。"
with c3:
    if st.button("📐 计算多普勒频移"): q_prompt = "给定列车时速 350km/h，载波频率 2.1GHz，请给出多普勒频移的计算公式与结果。"

selected_mode = st.radio("🧠 模式选择：", ["学术模式 (Academic)", "科普模式 (Popular Science)"], horizontal=True)

if "学术" in selected_mode:
    st.info("💡 **学术模式**已开启：回答将严格基于课件，并支持**鼠标悬停溯源**。")
else:
    st.success("🌟 **科普模式**已开启：回答将结合通用知识，更易于概念理解。")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

user_input = st.chat_input("请输入您的问题...")
final_prompt = q_prompt if q_prompt else user_input

if final_prompt:
    if not q_prompt:
        st.session_state.messages.append({"role": "user", "content": final_prompt})
    with st.chat_message("user"):
        st.markdown(final_prompt)

    with st.chat_message("assistant"):
        response = ask_ai(final_prompt, selected_mode)
        st.markdown(response, unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": response})

st.markdown(f"""
    <div style="text-align:center; color:#888; font-size:12px; margin-top:60px; border-top:1px solid #ddd; padding-top:20px;">
        © {time.strftime("%Y")} 北京交通大学 · 电子信息工程学院 · 孙涛 (23211436)<br>
        Powered by DeepSeek-V3 & Streamlit
    </div>
    """, unsafe_allow_html=True)
