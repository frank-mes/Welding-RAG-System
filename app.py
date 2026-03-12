import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (锁定稳定版模型)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # 强制锁定 1.5-flash 稳定版，避开低配额的预览版
        self.model_name = 'gemini-1.5-flash'
        self.model = genai.GenerativeModel(self.model_name)

    def get_solution(self, material, defect):
        max_retries = 3
        retry_delay = 5
        
        for i in range(max_retries):
            try:
                prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及修复建议。"
                # 显式调用模型生成内容
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                # 捕获 429 频率限制错误
                if "429" in str(e) and i < max_retries - 1:
                    st.warning(f"⚠️ 当前稳定版配额繁忙，正在进行第 {i+1} 次自动重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2 
                    continue
                else:
                    raise e

# ==========================================
# 2. DAO LAYER (数据访问层)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        self.repo = self.gh.get_user().get_repo(repo_name)

    def save_record(self, material, solution):
        # 自动创建 solutions 文件夹并按日期命名文件
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案备份\n- 材料: {material}\n- 时间: {datetime.datetime.now()}\n\n{solution}"
        try:
            self.repo.create_file(path, f"Welding solution for {material}", content, branch="main")
            return
