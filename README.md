# ⚙️ CoreTheory.ai

An AI-powered engineering study platform built with **Gradio** and **Gemini 2.5 Flash**.

## Features
- 💬 **Socratic Tutor** — Conversational AI with full memory that guides you through complex topics using analogies and targeted questions rather than direct answers
- 📝 **Exam Simulator** — Dynamically generates a graded 10-question MCQ exam from any topic or uploaded PDF, with difficulty mix (Easy / Normal / Complex)
- 🔗 **Smart Handoff** — Scoring ≤ 50% auto-populates the tutor with your missed topics for targeted review

## Live Demo
👉 [CoreTheory.ai on Hugging Face](https://huggingface.co/spaces/GauravDusa/CoreTheory.ai)

## Tech Stack
- Python
- Gradio 6
- Google GenAI SDK
- Gemini 2.5 Flash (JSON mode for structured quiz generation)

## Run Locally
```bash
git clone https://github.com/YOUR_USERNAME/CoreTheory.ai
cd CoreTheory.ai
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
python app.py
```

## How It Works
1. Enter any engineering or CS topic (or upload a study PDF)
2. Gemini generates 10 structured MCQ questions via JSON-mode prompting
3. Submit your answers — get instant grading with explanations
4. Score ≤ 50%? Missed topics are auto-loaded into the Socratic Tutor
