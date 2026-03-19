import streamlit as st
import pandas as pd
import plotly.express as px
import openai
from datetime import datetime, timedelta
import io
from fpdf import FPDF
import json

# ------------------------------
# Page Configuration
# ------------------------------
st.set_page_config(
    page_title="8-Quadrant Sales Matrix Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# Initialize Session State (Persistent Data)
# ------------------------------
if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "baseline_scores" not in st.session_state:
    st.session_state.baseline_scores = None
if "product_history" not in st.session_state:
    st.session_state.product_history = []

# ------------------------------
# Core Matrix Data Models & Logic
# ------------------------------
class NormalizedScores:
    def __init__(self, emotional_connection: float, perceived_value: float, trust: float, scarcity_exclusivity: float):
        self.emotional_connection = round(emotional_connection, 2)  # 0-100 scale
        self.perceived_value = round(perceived_value, 2)            # 0-100 scale
        self.trust = round(trust, 2)                                # 0-100 scale
        self.scarcity_exclusivity = round(scarcity_exclusivity, 2)  # 0-100 scale

# Official Priority-Based Quadrant Classification
def classify_quadrant(scores: NormalizedScores, custom_thresholds: dict = None) -> tuple[str, dict]:
    DEFAULT_THRESHOLDS = {
        "high_pv": 70, "low_pv": 30,
        "high_ec": 70, "low_ec": 30,
        "high_trust": 70, "low_trust": 30,
        "high_scarcity": 70
    }
    thresholds = custom_thresholds or DEFAULT_THRESHOLDS
    ec, pv, t, s = scores.emotional_connection, scores.perceived_value, scores.trust, scores.scarcity_exclusivity

    # Official priority order from your source document
    q1 = ec <= thresholds["low_ec"] and pv >= thresholds["high_pv"]
    q2 = ec >= thresholds["high_ec"] and t >= thresholds["high_trust"]
    q3 = ec <= thresholds["low_ec"] and pv <= thresholds["low_pv"]
    q4 = s >= thresholds["high_scarcity"] and ec <= thresholds["low_ec"]
    q5 = ec >= thresholds["high_ec"] and pv >= thresholds["high_pv"]
    q6 = pv <= thresholds["low_pv"] and ec >= thresholds["high_ec"]
    q7 = t <= thresholds["low_trust"] and pv <= thresholds["low_pv"] and ec <= thresholds["low_ec"]
    q8 = pv >= thresholds["high_pv"] and t >= thresholds["high_trust"]

    quadrant_name = None
    if q1:
        quadrant_name = "Quadrant 1: Value Proposition Zone"
    elif q2:
        quadrant_name = "Quadrant 2: Brand Loyalty Zone"
    elif q3:
        quadrant_name = "Quadrant 3: Deal Zone"
    elif q4:
        quadrant_name = "Quadrant 4: Scarcity and Exclusivity Zone"
    elif q5:
        quadrant_name = "Quadrant 5: Perceived Necessity Zone"
    elif q6:
        quadrant_name = "Quadrant 6: Buzz and Influence Zone"
    elif q7:
        quadrant_name = "Quadrant 7: Obscurity Zone"
    elif q8:
        quadrant_name = "Quadrant 8: Solution Zone"
    else:
        quadrant_name = "Unclassified Quadrant"

    return quadrant_name, thresholds

# Industry-Specific KPI Normalizer
def normalize_scores(industry: str, kpis: dict, is_prelaunch: bool = False) -> NormalizedScores:
    """Convert industry-specific KPIs to universal 0-100 scoring scale"""
    if is_prelaunch:
        # Use planned metrics for pre-launch forecasting
        pv = kpis.get("planned_pv_score", 50)
        ec = kpis.get("planned_ec_score", 20)
        trust = kpis.get("planned_trust_score", 20)
        scarcity = kpis.get("planned_scarcity_score", 20)
    else:
        # Use live performance metrics
        if industry == "General Retail":
            pv = (kpis.get("avg_review_rating", 2.5) / 5) * 100
            ec = (kpis.get("loyalty_participation_pct", 0.01) * 100)
            trust = (kpis.get("repeat_customer_pct", 0.1) * 100)
            scarcity = (kpis.get("limited_edition_pct", 0.0) * 100)
        elif industry == "Luxury Retail":
            pv = (kpis.get("brand_prestige_score", 50) / 100) * 100
            ec = (kpis.get("brand_advocate_pct", 0.2) * 100)
            trust = (kpis.get("warranty_success_rate", 0.95) * 100)
            scarcity = (kpis.get("limited_drop_score", 0.8) * 100)
        elif industry == "SaaS":
            pv = (kpis.get("nps", 30) / 100) * 100
            ec = (kpis.get("community_members_pct", 0.15) * 100)
            trust = (kpis.get("uptime_sla", 0.999) * 100)
            scarcity = (kpis.get("enterprise_only_pct", 0.1) * 100)
        elif industry == "Healthcare":
            pv = (kpis.get("patient_satisfaction_score", 70) / 100) * 100
            ec = (kpis.get("patient_loyalty_pct", 0.3) * 100)
            trust = (kpis.get("credentialing_score", 0.9) * 100)
            scarcity = (kpis.get("specialist_availability_score", 0.4) * 100)
        elif industry == "Financial Services":
            pv = (kpis.get("client_retention_rate", 0.8) * 100)
            ec = (kpis.get("personalized_service_score", 0.75) * 100)
            trust = (kpis.get("regulatory_compliance_score", 0.98) * 100)
            scarcity = (kpis.get("exclusive_product_pct", 0.2) * 100)
        else:
            pv = min(max(kpis.get("perceived_value", 50), 0), 100)
            ec = min(max(kpis.get("emotional_connection", 50), 0), 100)
            trust = min(max(kpis.get("trust", 50), 0), 100)
            scarcity = min(max(kpis.get("scarcity", 0), 0), 100)

    return NormalizedScores(ec, pv, trust, scarcity)

# ------------------------------
# AI-Powered Strategy Generator
# ------------------------------
def generate_optimization_strategy(quadrant: str, industry: str, persona: str, openai_api_key: str = None) -> dict:
    """Generate tailored, actionable strategies with optional AI enhancements"""
    base_strategies = {
        "Quadrant 1: Value Proposition Zone": {
            "core_focus": "Strengthen emotional connection while preserving high perceived value",
            "general_actions": [
                "Launch loyalty programs for repeat customers",
                "Highlight eco-friendly/societal benefits",
                "Send personalized post-purchase follow-ups",
                "Run limited-time promotions"
            ],
            "industry_tweaks": {
                "General Retail": "Add reusable packaging and market sustainability",
                "SaaS": "Launch a community forum for users",
                "Healthcare": "Share patient success stories"
            }
        },
        "Quadrant 2: Brand Loyalty Zone": {
            "core_focus": "Leverage exclusivity and storytelling to maintain loyalty",
            "general_actions": [
                "Launch VIP membership programs",
                "Share brand heritage content",
                "Offer limited-edition product variations",
                "Provide personalized support"
            ],
            "industry_tweaks": {
                "Luxury Retail": "Host exclusive in-store events for VIPs",
                "SaaS": "Offer early access to new features for enterprise customers"
            }
        },
        "Quadrant 3: Deal Zone": {
            "core_focus": "Build trust and elevate perceived value via social proof",
            "general_actions": [
                "Collect customer testimonials",
                "Upgrade product packaging",
                "Offer free trials/money-back guarantees",
                "Improve customer service training"
            ],
            "industry_tweaks": {
                "General Retail": "Partner with micro-influencers to showcase use cases",
                "SaaS": "Offer free onboarding sessions for new users"
            }
        },
        "Quadrant 4: Scarcity and Exclusivity Zone": {
            "core_focus": "Strengthen emotional attachment to drive long-term loyalty",
            "general_actions": [
                "Add personalized customization (engraving, sizing)",
                "Host exclusive buyer events",
                "Share behind-the-scenes product creation content",
                "Launch VIP access to limited drops"
            ],
            "industry_tweaks": {
                "General Retail": "Offer limited-time flash sales for exclusive products",
                "Luxury Retail": "Partner with luxury influencers for limited drops"
            }
        },
        "Quadrant 5: Perceived Necessity Zone": {
            "core_focus": "Reaffirm reliability and trustworthiness",
            "general_actions": [
                "Display third-party endorsements and certifications",
                "Share case studies and real-world results",
                "Launch referral programs",
                "Send proactive maintenance reminders"
            ],
            "industry_tweaks": {
                "Healthcare": "Publish clinical trial results and patient testimonials",
                "SaaS": "Share security compliance certifications (HIPAA)"
            }
        },
        "Quadrant 6: Buzz and Influence Zone": {
            "core_focus": "Improve perceived quality and reinforce brand reliability",
            "general_actions": [
                "Conduct product upgrades to address value gaps",
                "Add expert reviews and third-party validation",
                "Use transparent pricing models",
                "Partner with industry experts for endorsements"
            ],
            "industry_tweaks": {
                "General Retail": "Improve product durability and sustainable materials",
                "Social Media": "Run targeted ads highlighting product quality"
            }
        },
        "Quadrant 7: Obscurity Zone": {
            "core_focus": "Build brand recognition, trust, and perceived value",
            "general_actions": [
                "Partner with micro-influencers for niche outreach",
                "Create educational product content",
                "Offer introductory promotions or free samples",
                "Collect early testimonials via discount incentives"
            ],
            "industry_tweaks": {
                "SaaS": "Offer a free tier with core features",
                "Startups": "Launch a crowdfunding campaign to build social proof"
            }
        },
        "Quadrant 8: Solution Zone": {
            "core_focus": "Enhance emotional connection and exclusivity",
            "general_actions": [
                "Offer personalized product recommendations",
                "Launch exclusive VIP events or early access",
                "Provide dedicated account managers for high-value customers",
                "Launch tiered loyalty programs"
            ],
            "industry_tweaks": {
                "Financial Services": "Offer personalized financial planning sessions",
                "Healthcare": "Provide customized treatment plans for patients"
            }
        }
    }

    # Add AI-generated hyper-specific tactics if API key is provided
    if openai_api_key:
        try:
            openai.api_key = openai_api_key
            prompt = f"""
            Create a hyper-specific, actionable sales strategy for a product in {quadrant} for the {industry} industry targeting {persona} buyers.
            Include:
            1.  2 specific perception-shifting tactics to move to a higher-value quadrant
            2.  A 1-sentence pre-launch outreach script for pre-sales
            3.  3 measurable metrics to track success
            Keep it concise, practical, and tailored to small business owners.
            """
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            ai_tactics = response.choices[0].message.content
            base_strategies[quadrant]["ai_enhanced_tactics"] = ai_tactics
        except Exception as e:
            base_strategies[quadrant]["note"] = f"AI strategy unavailable: {str(e)}"

    return base_strategies[quadrant]

# ------------------------------
# Quadrant Visualization
# ------------------------------
def render_performance_chart(scores: NormalizedScores):
    """Render interactive bar chart of core perception metrics"""
    metric_data = pd.DataFrame({
        "Core Matrix Dimension": [
            "Emotional Connection",
            "Perceived Value",
            "Trust",
            "Scarcity/Exclusivity"
        ],
        "Score (0-100)": [
            scores.emotional_connection,
            scores.perceived_value,
            scores.trust,
            scores.scarcity_exclusivity
        ]
    })
    fig = px.bar(
        metric_data,
        x="Core Matrix Dimension",
        y="Score (0-100)",
        color="Score (0-100)",
        color_continuous_scale="Blues",
        range_y=[0, 100],
        title="Current Buyer Perception Scores"
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------
# Task Tracking System
# ------------------------------
def render_task_tracker():
    st.subheader("Optimization Task Tracker")
    task_col1, task_col2 = st.columns(2)
    with task_col1:
        new_task = st.text_input("Add New Optimization Task")
    with task_col2:
        due_date = st.date_input("Due Date", datetime.today())

    if st.button("Add Task") and new_task:
        st.session_state.tasks.append({
            "task_name": new_task,
            "due_date": due_date.strftime("%Y-%m-%d"),
            "completed": False
        })
        st.success(f"Added task: {new_task}")

    # Display and manage tasks
    if st.session_state.tasks:
        for idx, task in enumerate(st.session_state.tasks):
            col1, col2, col3 = st.columns([0.7, 0.2, 0.1])
            with col1:
                st.write(f"**{task['task_name']}** | Due: {task['due_date']}")
            with col2:
                if st.checkbox("Mark Complete", key=f"task_{idx}"):
                    st.session_state.tasks[idx]["completed"] = True
            with col3:
                if st.button("Delete", key=f"delete_{idx}"):
                    del st.session_state.tasks[idx]

# ------------------------------
# Exportable PDF Report Generator
# ------------------------------
def generate_pdf_report(quadrant: str, scores: NormalizedScores, strategy: dict, tasks: list) -> io.BytesIO:
    """Generate downloadable PDF report of product classification and strategy"""
    pdf = FPDF("portrait", "mm", "letter")
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, txt="8-Quadrant Sales Matrix Report", ln=True, align="C")
    pdf.ln(10)

    # Product Classification Details
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, txt="Product Quadrant Classification", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, txt=f"Current Quadrant: {quadrant}", ln=True)
