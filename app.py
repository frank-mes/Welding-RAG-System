import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (具备智能寻址与容错能力)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        self.api_enabled = False
        self.model_name = "None"
        
        if api_key and len(api_key) > 10:
            try:
                genai.configure(api_key=api_key)
                # 自动列出所有可用模型，解决 404 路径问题
                available_models = [m.name for m in genai.list_models() 
                                   if 'generateContent' in m.supported_generation_methods]
                
                # 定义优先级顺序
                priority = ['models/gemini-1.5-flash', 'gemini-1.5-flash', 'models/gemini-pro', 'gemini-pro']
                
                selected_model = None
                for p in priority:
                    if p in available_models:
                        selected_model = p
                        break
                
                if not selected_model and available_models:
                    selected_model = available_models[0]
                
                if selected_model:
                    self.model = genai.GenerativeModel(selected_model)
                    self.model_name = selected_model
                    self.api_enabled = True
                    st.sidebar.success(f"已连接引擎: {selected_model}")
                else:
                    st.sidebar.error("❌ 该 Key 未授权任何可用模型")
            except Exception as e:
                st.sidebar.warning(f"⚠️ 引擎初始化失败: {e}")

    def get_solution(self, material, defect):
        if self.api_enabled:
            try:
                prompt = (f"你是一位资深的国际焊接工程师(IWE)。请针对材料【{material}】"
                         f"出现的【{defect}】缺陷，提供失效分析及详细的工艺修复建议。"
                         f"请使用 Markdown 格式输出，包含：原因分析、工艺参数调整、焊后检验要求。")
                
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 达到 API 频率限制，进入本地专家库...")
                else:
                    st.error(f"❌ AI 生成失败: {e}")
        
        # 补全了之前断掉的 f-string
        time.sleep(1.5) 
        return f"### 🛡️ 专家建议 (本地库备份)\n\n**缺陷分析**：针对 {material} 的 {defect} 缺陷，可能是热输入不当导致。\n\n**修复建议**：\n1. 清理坡口油脂与氧化皮；\n2. 严格控制层间温度；\n3. 推荐使用小电流多层多道焊。"

# ==========================================
# 2. DAO LAYER (数据存档)
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
                contents = self.repo.get_contents(path)
                self.repo.update_file(path, f"Update {material}", content, contents.sha, branch="main")
                return f"已更新备份: {path}"
            except:
                self.repo.create_file(path, f"Create {material}", content, branch="main")
                return f"已新建备份: {path}"
        except Exception as e:
            return f"同步失败: {str(e)}"

# ==========================================
# 3. VIEW (Streamlit 界面)
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家系统", page_icon="👨‍🏭")
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    st.markdown("---")

    key = st.secrets.get("GEMINI_KEY", "")
    token = st.secrets.get("GH_TOKEN", "")
    repo = "welding-rag-system" 

    svc = WeldingService(key)

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            material = st.text_input("材料牌号")
        with col2:
            defect = st.text_input("缺陷类型")

    if st.button("开始 AI 推理诊断", type="primary", use_container_width=True):
        if not material or not defect:
            st.warning("⚠️ 请输入完整信息。")
            return

        with st.status("正在调取焊接专家模型...") as status:
            solution = svc.get_solution(material, defect)
            status.update(label="诊断完成！", state="complete")
        
        st.subheader("💡 专家建议方案")
        st.markdown(solution)

        if token:
            dao = WeldingDAO(token, repo)
            save_msg = dao.save_record(material, solution)
            st.toast(save_msg, icon="💾")

if __name__ == "__main__":
    main()
