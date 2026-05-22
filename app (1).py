import os
import json
import gradio as gr
from pypdf import PdfReader
from google import genai
from google.genai import types

# ── SETUP ──────────────────────────────────────────────────────────────────────
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

TUTOR_INSTRUCTION = """
You are an expert engineering professor conducting a Socratic dialogue.
Help the user master complex topics through guided discovery.
- Never give the full solution immediately
- Break topics down and explain core principles using practical analogies
- Use proper LaTeX notation for all formulas ($ for inline, $$ for blocks)
- Reference prior conversation turns to maintain continuity
- End every turn with exactly ONE targeted guiding question
"""

# ── UTILITIES ──────────────────────────────────────────────────────────────────
def extract_pdf_text(file_obj):
    if file_obj is None:
        return ""
    try:
        reader = PdfReader(file_obj.name)
        text = "".join(page.extract_text() + "\n" for page in reader.pages)
        return text[:15000]
    except Exception:
        return ""

def build_missed_topics_message(quiz_data, user_answers):
    missed = []
    for i, item in enumerate(quiz_data):
        if i >= len(user_answers):
            break
        if user_answers[i] != item.get('correct_option', ''):
            q_text = item.get('question_text', item.get('question', f'Question {i+1}'))
            missed.append(f"- {q_text}")
    if not missed:
        return ""
    joined = "\n".join(missed)
    return (
        f"I just completed an exam and got these questions wrong. "
        f"Please help me understand the underlying concepts one by one:\n\n{joined}"
    )

# ── TUTOR BACKEND ──────────────────────────────────────────────────────────────
def tutor_chat(message, history):
    if not message or not message.strip():
        return "Please type a question or topic you'd like to explore."
    try:
        contents = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=TUTOR_INSTRUCTION,
                temperature=0.7
            )
        )
        return response.text
    except Exception as e:
        return f"⚠️ Tutor error: {str(e)}"

# ── QUIZ BACKEND ───────────────────────────────────────────────────────────────
def generate_interactive_quiz(text_input, file_obj):
    context_source = (text_input or "").strip()
    if file_obj is not None:
        pdf_text = extract_pdf_text(file_obj)
        if pdf_text.strip():
            context_source = pdf_text

    def empty_return(msg):
        return (
            [[]]
            + [gr.update(visible=False)] * 10
            + [gr.update(value="")] * 10
            + [gr.update(choices=[], value=None, visible=False)] * 10
            + [gr.update(value="", visible=False)] * 10
            + [gr.update(value=msg, visible=True), gr.update(visible=False)]
        )

    if not context_source:
        return empty_return("⚠️ Please enter a topic or upload a PDF.")
    if len(context_source) < 5:
        return empty_return("⚠️ Topic is too short. Please be more specific (e.g. 'Binary Search Trees').")

    prompt = f"""
    You are an expert engineering and computer science exam generator.
    Analyze the following source material and generate exactly 10 multiple-choice questions.
    Ensure a mix of difficulty: 3 Easy, 4 Normal, and 3 Complex questions.

    Source Material: {context_source[:7000]}

    Output a clean JSON array of exactly 10 objects. Keep all strings flat with no newline escape tokens:
    [
      {{
        "question_text": "Question 1: What is the primary purpose of data encapsulation in OOP?",
        "options": ["A) To abstract system memory", "B) To restrict direct access to object components", "C) To permit structural polymorphism", "D) To minimize Big-O runtime complexity"],
        "correct_option": "B) To restrict direct access to object components",
        "explanation": "Encapsulation wraps data and methods together, hiding internal object states."
      }}
    ]
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4
            )
        )
        quiz_data = json.loads(response.text.strip())

        out_groups, out_questions, out_radios, out_explanations = [], [], [], []
        for i in range(10):
            if i < len(quiz_data):
                item = quiz_data[i]
                q_body = item.get('question_text', item.get('question', f"Question {i+1}"))
                out_groups.append(gr.update(visible=True))
                out_questions.append(gr.update(value=f"### {q_body}"))
                out_radios.append(gr.update(choices=item.get('options', []), value=None, visible=True))
                out_explanations.append(gr.update(value="", visible=False))
            else:
                out_groups.append(gr.update(visible=False))
                out_questions.append(gr.update(value=""))
                out_radios.append(gr.update(choices=[], value=None, visible=False))
                out_explanations.append(gr.update(value="", visible=False))

        return (
            [quiz_data]
            + out_groups
            + out_questions
            + out_radios
            + out_explanations
            + [gr.update(value=f"✅ Generated a {len(quiz_data)}-question exam. Good luck!", visible=True),
               gr.update(visible=True)]
        )

    except Exception as e:
        return empty_return(f"❌ Generation Error: {str(e)}")

# ── GRADING + HANDOFF ──────────────────────────────────────────────────────────
def grade_quiz(quiz_data, *user_answers):
    if not quiz_data:
        return (
            [gr.update(value="⚠️ No quiz data. Please generate a quiz first.", visible=True)]
            + [gr.update(visible=False)] * 10
            + [gr.update(visible=False)]
        )

    score = 0
    total = len(quiz_data)
    out_exps = []

    for i in range(10):
        if i < total:
            item = quiz_data[i]
            user_ans = user_answers[i]
            correct_ans = item.get('correct_option', '')
            if user_ans == correct_ans:
                score += 1
                mark = "✅ **Correct!**"
            else:
                mark = f"❌ **Incorrect.** Correct answer: **{correct_ans}**"
            full_exp = f"{mark}\n\n*Explanation:* {item.get('explanation', 'No explanation available.')}"
            out_exps.append(gr.update(value=full_exp, visible=True))
        else:
            out_exps.append(gr.update(visible=False))

    pct = (score / total) * 100 if total > 0 else 0

    if pct <= 50:
        score_msg = (
            f"## 📉 Final Score: {score}/{total} ({pct:.0f}%)\n\n"
            f"**Score is 50% or below.** The tutor handoff box below has been pre-loaded "
            f"with your missed topics — copy it into the **Socratic Tutor** tab to start your review!"
        )
    else:
        score_msg = (
            f"## 🏆 Final Score: {score}/{total} ({pct:.0f}%)\n\n"
            f"**Great job!** You have a strong grasp of this material."
        )

    missed_msg = build_missed_topics_message(quiz_data, list(user_answers))
    tutor_update = (
        gr.update(value=missed_msg, visible=True)
        if (pct <= 50 and missed_msg)
        else gr.update(visible=False)
    )

    return [gr.update(value=score_msg, visible=True)] + out_exps + [tutor_update]

# ── GRADIO UI ──────────────────────────────────────────────────────────────────
with gr.Blocks() as demo:

    quiz_state = gr.State([])

    gr.Markdown("""# ⚙️ Advanced Engineering Learning Suite
*Powered by Gemini 2.5 Flash — Socratic Tutor + Interactive Exam Simulator*""")

    with gr.Tab("💬 Socratic Tutor"):
        gr.Markdown(
            "Ask any engineering or CS topic. The tutor **remembers the full conversation** "
            "and guides you with questions rather than direct answers.\n\n"
            "_Tip: If you scored ≤ 50% on the exam, copy the pre-loaded message from the "
            "handoff box below into the chat to start your review._"
        )
        gr.ChatInterface(fn=tutor_chat)

    with gr.Tab("📝 Interactive Exam Simulator"):
        gr.Markdown(
            "Enter an engineering or CS topic, or upload a study PDF. "
            "A 10-question graded exam will be generated live."
        )
        with gr.Row():
            topic_input = gr.Textbox(
                label="Enter Topic",
                placeholder="e.g. Automata Theory, Binary Trees, OS Scheduling...",
                scale=3
            )
            file_input = gr.File(
                label="Or Upload PDF",
                file_types=[".pdf"],
                scale=1
            )

        generate_btn = gr.Button("🚀 Generate Exam", variant="primary", size="lg")
        status_text = gr.Markdown(visible=False)

        q_groups, q_texts, q_radios, q_explanations = [], [], [], []
        for i in range(10):
            with gr.Group(visible=False) as g:
                q_text = gr.Markdown(value=f"### Question {i+1}")
                q_radio = gr.Radio(choices=[], label="Select your answer:")
                q_exp = gr.Markdown(visible=False)
                q_groups.append(g)
                q_texts.append(q_text)
                q_radios.append(q_radio)
                q_explanations.append(q_exp)

        submit_btn = gr.Button("📊 Submit Exam for Grading", variant="stop", visible=False, size="lg")
        score_display = gr.Markdown(visible=False)

        tutor_handoff_box = gr.Textbox(
            label="📚 Missed Topics — Copy this into the Socratic Tutor tab to start your review",
            lines=6,
            visible=False,
            interactive=False
        )

    # ── WIRE EVENTS ───────────────────────────────────────────────────────────
    generate_outputs = (
        [quiz_state]
        + q_groups
        + q_texts
        + q_radios
        + q_explanations
        + [status_text, submit_btn]
    )
    generate_btn.click(
        fn=generate_interactive_quiz,
        inputs=[topic_input, file_input],
        outputs=generate_outputs
    )

    grade_outputs = [score_display] + q_explanations + [tutor_handoff_box]
    submit_btn.click(
        fn=grade_quiz,
        inputs=[quiz_state] + q_radios,
        outputs=grade_outputs
    )

# ── LAUNCH ────────────────────────────────────────────────────────────────────
demo.launch(theme=gr.themes.Soft())
