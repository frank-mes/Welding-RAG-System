import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (智能引擎层)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        self.api_enabled = False
        self.model_name = "None"
        
        if api_key and len(api_key) > 10:
            try:
                genai.configure(api_key=api_key)
                # 自动检测可用模型
                models = [m.name for m in genai.list_models() 
                         if 'generateContent' in m.supported_generation_methods]
                
                # 优先级排序
                priority = ['models/gemini-1.5-flash', 'models/gemini-2.0-flash', 'models/gemini-pro']
                target = next((p for p in priority if p in models), models[0] if models else None)
                
                if target:
                    self.model = genai.GenerativeModel(target)
                    self.model_name = target
                    self.api_enabled = True
                    st.sidebar.success(f"✅ 已连接引擎: {target}")
            except Exception as e:
                st.sidebar.warning(f"⚠️ 引擎待机中: {e}")

    def get_solution(self, material, defect):
        if not self.api_enabled:
            return self.get_mock_response(material, defect)

        # 针对免费版 API 的“暴力”重试策略
        max_retries = 3
        wait_time = 10 
        
        for i in range(max_retries):
            try:
                # 增加一个微小的随机延迟，防止瞬时并发过高
                time.sleep(1) 
                
                prompt = f"""你是一位资深国际焊接工程师(IWE)。
                请针对材料【{material}】的【{defect}】缺陷进行深度分析。
                要求：
                1. 分析该材料的焊接性及缺陷成因（涉及微观组织）。
                2. 给出具体的预热温度、层间温度和后热(PWHT)参数。
                3. 列出推荐的焊材型号及保护气体配比。
                请使用专业的 Markdown 格式输出。"""
                
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    return response.text
                
            except Exception as e:
                if "429" in str(e) and i < max_retries - 1:
                    st.warning(f"⚠️ 触发频率限制，正在进行第 {i+1} 次深度冷却（{wait_time}秒）...")
                    time.sleep(wait_time)
                    wait_time += 15 # 逐步增加冷却时间
                    continue
                else:
                    st.error(f"❌ AI 实时生成失败: {e}")
                    break
        
        return self.get_mock_response(material, defect)

    def get_mock_response(self, material, defect):
        """本地兜底方案库"""
        return f"""### 🛡️ 专家建议 (本地库备份)
        
**注意**：当前 AI 引擎繁忙，为您自动匹配基础修复方案。

**针对 {material} 的 {defect} 分析**：
1. **成因**：通常与热输入量控制不当或冷速过快有关。
2. **工艺建议**：
    - 严格执行预热工艺，建议温度控制在 150°C-250°C 之间。
    - 采用小电流、多层多道焊，减少晶粒粗化。
    - 焊后立即进行消氢处理（250°C x 2h）。
3. **检验**：建议进行 100% 超声波探伤 (UT) 或磁粉探伤 (MT)。"""

# ==========================================
# 2. DAO LAYER (数据持久化)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        try:
            self.gh = Github(token)
            self.repo = self.gh.get_user().get_repo(repo_name)
            self.valid = True
        except:
            self.valid = False

    def save_record(self, material, solution):
        if not self.valid: return "GitHub 未配置"
        
        date_str = datetime.date.today().isoformat()
        path = f"solutions/{material}_{date_str}.md"
        content = f"# 焊接专家方案备份\n\n- 材料: {material}\n- 存档日期: {datetime.datetime.now()}\n\n---\n\n{solution}"
        
        try:
            try:
                # 如果文件已存在则更新
                contents = self.repo.get_contents(path)
                self.repo.update_file(path, f"Update {material}", content, contents.sha, branch="main")
                return f"✅ 已更新云端档案: {path}"
            except:
                # 否则新建
                self.repo.create_file(path, f"Create {material}", content, branch="main")
                return f"✅ 已新建云端档案: {path}"
        except Exception as e:
            return f"❌ 同步失败: {str(e)}"

# ==========================================
# 3. UI LAYER (Streamlit 界面)
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家系统", page_icon="👨‍🏭", layout="centered")
    
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    st.caption("工业级 AI 辅助决策系统 | 2026 稳定版")
    st.markdown("---")

    # 获取配置
    gemini_key = st.secrets.get("GEMINI_KEY", "")
    gh_token = st.secrets.get("GH_TOKEN", "")
    repo_name = "welding-rag-system"

    # 初始化服务
    svc = WeldingService(gemini_key)

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            material = st.text_input("材料牌号", placeholder="如: 12Cr1MoV")
        with col2:
            defect = st.text_input("缺陷类型", placeholder="如: 再热裂纹")

    if st.button("开始 AI 推理诊断", type="primary", use_container_width=True):
        if not material or not defect:
            st.warning("⚠️ 请输入完整信息。")
            return

        with st.status("正在咨询 AI 专家引擎...", expanded=True) as status:
            solution = svc.get_solution(material, defect)
            status.update(label="诊断报告生成完毕！", state="complete")
        
        # 显示结果
        st.markdown("---")
        st.subheader("💡 专家建议方案")
        st.markdown(solution)

        # 执行 GitHub 存档
        if gh_token:
            dao = WeldingDAO(gh_token, repo_name)
            with st.spinner("正在同步至 GitHub 云端..."):
                save_msg = dao.save_record(material, solution)
                st.toast(save_msg)

if __name__ == "__main__":
    main()
