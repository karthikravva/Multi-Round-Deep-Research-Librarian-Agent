import os
import json
import time
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
import google.generativeai as genai
from urllib.parse import quote_plus
import re
from fpdf import FPDF
import tempfile
import gradio as gr

@dataclass
class ResearchConfig:
    gemini_api_key: str
    max_sources: int = 10
    search_delay: float = 1.0

class DeepResearchSystem:
    def __init__(self, config: ResearchConfig):
        self.config = config
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def search_web(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        try:
            encoded_query = quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_redirect=1"
            response = requests.get(url, timeout=10)
            data = response.json()
            results = []
            if 'RelatedTopics' in data:
                for topic in data['RelatedTopics'][:num_results]:
                    if isinstance(topic, dict) and 'Text' in topic:
                        results.append({
                            'title': topic.get('Text', ''),
                            'url': topic.get('FirstURL', ''),
                            'snippet': topic.get('Text', '')
                        })
            return results
        except Exception:
            return []

    def conduct_research(self, query: str, depth: str = "standard") -> Dict[str, Any]:
        print(f"🔍 Starting research on: {query}")
        search_rounds = {"basic": 1, "standard": 2, "deep": 3}.get(depth, 2)
        sources_per_round = {"basic": 3, "standard": 5, "deep": 7}.get(depth, 5)
        all_sources = []
        search_queries = [query]
        if depth in ["standard", "deep"]:
            try:
                related_prompt = f"Generate 2 related search queries for: {query}. One line each."
                response = self.model.generate_content(related_prompt)
                additional_queries = [q.strip() for q in response.text.split('\n') if q.strip()][:2]
                search_queries.extend(additional_queries)
            except:
                pass
        
        for i, search_query in enumerate(search_queries[:search_rounds]):
            print(f"🔎 Search round {i+1}: {search_query}")
            sources = self.search_web(search_query, sources_per_round)
            all_sources.extend(sources)
            time.sleep(self.config.search_delay)

        unique_sources = list({source['url']: source for source in all_sources if source['url']}.values())
        print(f"📊 Analyzing {len(unique_sources)} unique sources...")
        
        analysis_prompt = f"Analyze the following research content on '{query}'. Provide 3-4 key themes and 3-4 main insights. Format as JSON with keys: themes, insights.\n\nContent: " + " ".join([s['snippet'] for s in unique_sources])[:4000]
        try:
            analysis_response = self.model.generate_content(analysis_prompt)
            analysis = json.loads(analysis_response.text)
        except:
            analysis = {'themes': ["Information synthesis"], 'insights': ["Comprehensive analysis"]}

        print("📝 Generating comprehensive report...")
        report_prompt = f"Create a comprehensive research report on '{query}' based on the following sources and analysis:\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['snippet'][:200]}" for s in unique_sources[:5]]) + f"\n\nAnalysis:\nThemes: {analysis['themes']}\nInsights: {analysis['insights']}\n\nStructure the report with an Executive Summary, Key Findings, Detailed Analysis, and Conclusions."
        
        try:
            report_response = self.model.generate_content(report_prompt)
            report_text = report_response.text
        except:
            report_text = f"# Research Report: {query}\n\n## Executive Summary\n\nNo report generated due to API error. A comprehensive analysis was attempted on {len(unique_sources)} sources."

        return {
            'query': query,
            'sources_found': len(unique_sources),
            'report': report_text,
            'sources': unique_sources
        }

def setup_research_system(api_key: str) -> DeepResearchSystem:
    config = ResearchConfig(gemini_api_key=api_key, max_sources=15, search_delay=0.5)
    return DeepResearchSystem(config)

def research_agent_interface(query, depth):
    API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE" 
    
    researcher = setup_research_system(API_KEY)
    results = researcher.conduct_research(query, depth=depth)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    report_text = results['report'].replace("*", "").replace("##", "").replace("###", "")
    pdf.multi_cell(0, 10, report_text.encode('latin-1', 'replace').decode('latin-1'))
    
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "research_report.pdf")
    pdf.output(file_path)
    
    return file_path

iface = gr.Interface(
    fn=research_agent_interface,
    inputs=[
        gr.Textbox(label="Enter Research Query", placeholder="e.g., The future of quantum computing"),
        gr.Radio(["basic", "standard", "deep"], label="Research Depth", value="standard")
    ],
    outputs=gr.File(label="Download Report as PDF"),
    title="Deep Research Agent",
    description="An AI agent that performs multi-round research and generates a comprehensive PDF report."
)

if __name__ == "__main__":
    iface.launch()
