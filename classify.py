import os
from dotenv import load_dotenv
load_dotenv()

import json
import requests

from schema import EmailClassifier, Label

OLLAMA_URL = os.environ["OLLAMA_URL"]
MODEL_NAME = os.environ["MODEL_NAME"]

SYSTEM_PROMPT = """
You are an email classification assistant. Given the sender and content of one email, classify it into exactly one label.
 
Label definitions:
- job_postings: recruiter outreach, job alerts, application status updates
- coding_contests: competitive programming contests (Codeforces, LeetCode, CodeChef, etc.)
- hackathons: hackathon announcements, invitations, or related updates
- food_delivery: order confirmations, delivery updates from food apps (Swiggy, Zomato, etc.)
- newsletter: recurring digest/newsletter content the user is subscribed to
- security: verification codes, sign-in alerts, password reset emails, account security notices
- spam: promotions, meetup invites, marketing unrelated to the above
- delete: content that is clearly junk and not worth even reviewing, but doesn't cleanly fit "spam" (expired notices, old automated receipts, etc.)
- unknown: anything you cannot confidently place in any label above
 
Think briefly about the signal in the reasoning field, then choose exactly one label. Only use information present in the email; do not guess facts not stated.
"""

def build_user_prompt(sender: str, subject: str, body: str) -> str:
    return (
        f"Sender: {sender}\n"
        f"Subject: {subject}\n"
        f"Body: \n{body}"
    )

def classify_email(sender: str, subject: str, body: str) -> EmailClassifier:
    user_prompt = build_user_prompt(sender, subject, body)
    schema = EmailClassifier.model_json_schema()

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "format": schema,
        "options": {
            "temperature":0
        },
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    raw_content = response.json()["message"]["content"]
    parsed = json.loads(raw_content)
    return EmailClassifier.model_validate(parsed)


if __name__ == "__main__":
    result = classify_email(
        sender="no-reply@m.learn.coursera.org",
        subject="Stanford Online: AI Courses for Builders, Leaders, and Healthcare Innovators",
        body= """
AI is moving fast enough that no two people begin at the same starting point. Some of you want to understand the math behind generative models, others want to build your first AI agent, and others are trying to figure out what responsible AI actually looks like in a clinical setting. 

This month's lineup covers all of that ground: technical deep dives like Reinforcement Learning and Natural Language Processing with Deep Learning, approachable options like Introduction to Agentic AI and Vibe Coding for newcomers, and specialized programs in AI in Healthcare and Digital Health Product Development for professionals applying AI to patient care.

Wherever you're starting from, there's a course designed to meet you there. Take a look at what's available for enrollment, and save your spot.

Build, Design, and Deploy Intelligent AI Agents

Our new Agentic AI course guides you through end-to-end agent workflows, covering the latest techniques in self-improving AI agent tool use, reasoning, and planning. You’ll follow the same graduate-level curriculum taught on campus in CS329A, led by Adjunct Professor Aakanksha Chowdhery and Assistant Professor Azalia Mirhoseini, adapted for working professionals. 

Learn more and apply >>

Learn to Build the AI Models Everyone Else Is Using

You know AI is reshaping how organizations compete, but there's a real gap between using off-the-shelf AI tools and actually being able to build, debug, and optimize your own models. 

Our Artificial Intelligence Professional Program gives you rigorous, hands-on coverage of machine learning, deep learning, NLP, reinforcement learning, computer vision, and more — so you can build original AI models and algorithms, fine-tune them for real performance, and implement generative language models with confidence.

Learn program details >>

UPCOMING AI COURSES

Reinforcement Learning (XCS234) | October 19 - January 11 | $2,045

Discover the reinforcement learning techniques powering everything from robotics to today's most advanced large language models (LLMs), including reinforcement learning from human feedback (RLHF) and Direct Preference Optimization. 

Learn more and enroll >>

Natural Language Processing with Deep Learning (XCS224N) | October 26 - January 17 | $2,045

Master the neural network algorithms behind today's LLMs, making large-scale word predictions with language models, recurrent neural networks (RNNs), and neural machine translation. 

Learn more and enroll >>

Deep Reinforcement Learning (XCS224R) | November 2 - January 24 | $2,045

Train real-world agents using imitation learning, offline and model-based RL, and techniques for generalizable behavior like goal-conditioned and meta-RL. 

Learn more and enroll >>

Machine Learning (XCS229) | November 16 - February 7 | $2,045

Go from theory to practice as you construct machine learning algorithms from the ground up. From supervised and unsupervised methods to deep learning foundations, you will explore real-world applications.

Learn more and enroll >>

Artificial Intelligence: Principles and Techniques (XCS221) | January 25 - April 4 | $2,045

Gain a broad, hands-on foundation in modern AI. You will learn to design, test, and implement the algorithms behind problem-solving, reasoning, learning, and interaction. 

Learn more and enroll >>

Demystifying Machine Learning and Generative AI | October 1 | 8 weeks

Go beyond the technical jargon with a non-technical introduction to machine learning, deep learning, and generative AI. Explore how AI systems work, from regression and neural networks to ChatGPT, Claude, agentic AI, and AI safety. No coding experience required.

Learn more and enroll >>

AI in Healthcare: From Innovation to Impact | October 15 | 6 weeks

Explore what it takes to turn AI innovation into meaningful healthcare impact. Examine real-world applications, clinical workflows, quality and outcomes, and where AI is improving care—or adding complexity without value.

Learn more and enroll >>

Vibe Coding: Using AI for Programming | October 29 | 5 weeks

Build apps and websites with AI—no coding background required. Learn to write effective prompts, refine AI-generated output, troubleshoot issues, and turn your ideas into functional projects while staying in control of the creative process.

Learn more and enroll >>

Applications of Machine Learning in Medicine: A Deep Dive with Stanford Health Care's Chief Data Scientist

New technology doesn't automatically translate into value, especially in healthcare. 

With an emphasis on real-world utility and responsible AI, this two-course, hands-on program equips you with the skills to design, evaluate, and launch machine learning solutions that turn complex data into meaningful insights, ultimately improving patient care and outcomes.

Learn more >>

AI in Healthcare: Build Your Foundation

AI is reshaping diagnosis, personalized care, and clinical decision-making, but building models is only half the story. How do you deploy AI in the clinic safely, ethically, and in a way that builds trust?

Learn from Stanford Medicine faculty across five courses covering the healthcare system, clinical data, and machine learning fundamentals. Work through a patient-journey capstone and gain the cross-disciplinary fluency to bring AI into healthcare effectively.

Learn more >>

Digital Health Product Development

Healthcare is in the midst of a digital revolution. Mobile health apps, wearables, telehealth, digital health records, and personalized medicine are transforming how care is delivered.

This course will empower you to identify unmet clinical needs, develop ideas into products, and bring those products to market, while learning to navigate intellectual property rights and common quality and regulatory pitfalls. 

Learn more >>

AI Literacy for Educators: Starts October 6th

In this 4-session course, explore what AI Literacy means and why it matters. Deepen your understanding of GenAI tools, including the ethical responsibilities, risks, and opportunities AI presents for teaching and learning, while developing a principled stance for your classroom and practice. 

Learn More & Enroll >>

21st-Century Teaching & Learning: Data Science 

In this self-paced course, explore what data literacy means and why it matters in today’s data-filled world. Learn practical ways to help students analyze, visualize, and make sense of data across subject areas, while developing engaging learning experiences that build students’ confidence and understanding. 

Learn More & Enroll >> 

Stanford Online is brought to you by the Stanford Engineering Center for Global & Online Education


"""
    )
    print(result)