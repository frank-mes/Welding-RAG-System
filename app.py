import streamlit as st
import google.generativeai as genai
from github import Github
import datetime

# ==========================================
# 1. SERVICE LAYER (业务逻辑层)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # 自动尝试获取当前可用的最新模型
        self.model_name = self._get_best_model()
        self.model = genai.GenerativeModel(self.model_name)

    def _get_best_model(self):
        """自动检测账户下可用的最佳模型"""
        try:
            available_models = [m.name for m in genai.list_models() 
                               if 'generateContent' in m.supported_generation_methods]
            # 优先级排序：gemini-pro 是最稳妥的兼容项
            for preferred in ['models/gemini-1.5-flash', 'models/gemini-pro']:
                if preferred in available_models:
                    return preferred
            return available_models[0] if available_models else 'gemini-pro'
        except:
            return 'gemini-pro' # 兜底策略

    def get_solution(self, material, defect):
        prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及详细的修复建议。"
        response = self.model.generate_content(prompt)
        return response.text

# ==========================================
# 2. DAO LAYER (数据访问层)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        # 获取当前授权用户下的仓库
        self.repo = self.gh.get_user().get_repo
