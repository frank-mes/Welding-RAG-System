import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (深度锁定稳定版)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        # 初始化配置
        genai.configure(api_key=api_key)
        # 强制指定具体版本号，不给系统留任何“猜测”空间
        self.model_name = 'gemini-1.5-flash' 
        self.model = genai.GenerativeModel(model_name=self.model_name)

    def get_solution(self, material, defect):
        max_retries = 3
        wait_time = 10 # 增加初次等待时间，因为 429 意味着你需要更久的冷却
        
        for i in range(max_retries):
            try:
                prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及修复建议。"
                # 显式设置安全设置（有时候默认设置会导致异常）
                response = self.model.generate_content(prompt)
                
                if not response.text:
                    raise Exception("模型返回了空内容")
                return response.text
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg and i < max_retries - 1:
                    st.warning(f"⚠️ 触发频率限制 (429)。由于是免费版，请静候 {wait_time} 秒，系统会自动重试...")
                    time.sleep(wait_time)
                    wait_time *= 2 # 指数退避：10s -> 20s
                    continue
                else:
                    raise e

# ==========================================
# 2. DAO LAYER (保持稳定)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        self.repo = self.gh.get_user().get_repo(repo_name)

    def save_record(self, material, solution):
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案备份\n- 材料: {material}\n- 时间: {datetime.datetime.now()}\n\n{solution}"
        try:
            # 检查文件夹是否存在（GitHub API 限制：如果路径不存在会自动创建）
            self.repo.create_file(path, f"Upload {material} solution", content, branch="main")
            return path
        except Exception as e:
            if "already exists" in str(e): return "已存在相同备份"
            raise e

# ==========================================
# 3. UI LAYER
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家", page_icon="👨‍🏭")
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    
    # 强制状态显示
    st.sidebar.info(f"当前引擎: Gemini 1.5 Flash (稳定版)")
    
    with st.container(border=True):
        mat = st.text_input("材料牌号")
        dfc = st.text_input("缺陷类型")

    if st.button("生成专家方案", type="primary", use_container_width=True):
        if not mat or not dfc:
            st.warning("内容不能为空")
            return

        try:
            # 执行推理
            svc = WeldingService(st.secrets["GEMINI_KEY"])
            with st.status("正在咨询 AI 专家...", expanded=True) as status:
                res = svc.get_solution(mat, dfc)
                status.update(label="生成成功！", state="complete")
            
            st.markdown("---")
            st.markdown(res)

            # 执行存档
            dao = WeldingDAO(st.secrets["GH_TOKEN"], "welding-rag-system")
            path = dao.save_record(mat, res)
            st.toast(f"已存档至 GitHub: {path}")

        except Exception as e:
            if "429" in str(e):
                st.error("❌ 免费配额暂时耗尽。请彻底关闭此页面，5 分钟后再试。")
                st.info("💡 建议：去 Google AI Studio 重新生成一个新的 API Key 填入 Secrets，有时能绕过特定 Key 的限流。")
            else:
                st.error(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    main()
