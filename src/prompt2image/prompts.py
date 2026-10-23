"""The texts sent to the models. Image models follow English best, so every prompt is in English."""

# Rewrites a short idea into a detailed prompt, with a chat model.
ENHANCE_INSTRUCTION = (
    "You write prompts for an image generation model. Rewrite the user's idea as one detailed English prompt: "
    "subject, setting, composition, lighting and colors, 40 to 90 words. Do not name an art style, the user picks "
    "it separately. Never ask for text, letters or words in the picture. Answer with the prompt only."
)

# Appended to a generation prompt unless lettering is wanted.
NO_TEXT = "The picture shows no writing of any kind, only shapes, people and objects."

# Style sentences, placed before the subject.
STYLES = {
    "none": "",
    "photo": "Photorealistic photograph, natural light, sharp focus, realistic details.",
    "illustration": "Clean editorial illustration, clear shapes, harmonious colors.",
    "sketch": "Hand-drawn pencil sketch, loose confident lines, light shading, plain white paper.",
    "watercolor": "Soft watercolor painting, gentle color washes, visible paper texture.",
    "3d": "3D render, soft studio lighting, smooth materials, subtle shadows.",
    "flat": "Flat vector illustration, simple geometric shapes, solid colors, no gradients.",
}

# Reading tasks for describe.
TASKS = {
    "describe": ("Describe the image in detail: what it shows, people, objects, setting, colors and mood. "
                 "If it is a chart or diagram, also name what its axes or parts show, the key values and the main "
                 "takeaway. Use short paragraphs."),
    "text": ("Transcribe all text that is visible in the image exactly, keep its order and line breaks. "
             "If there is no text, say so in one sentence."),
    "question": "Answer the question about the image precisely and only from what the image shows.",
}

# Rules that hold for every reading task.
BASE_RULES = ("You help users with visual content. Only state what is visible, add nothing and do "
              "not guess what is not visible. Do not use semicolons or any type of dash, only periods, commas and "
              "question marks.")

# Answer languages by code. Any other value is used as the language name itself, for example "French".
LANGUAGES = {"de": "German", "en": "English"}

# The general reading instruction, used when no task is chosen. A task replaces it, because its
# call for detail and for the language of the image would override the chosen task and language.
GENERAL_INSTRUCTION = (
    "You are an expert assistant helping users analyze visual content.\n"
    "Describe the image in detail.\n"
    "Follow these rules strictly:\n"
    "Rule 1: Transcribe all visible text verbatim.\n"
    "Rule 2: Explain diagrams, charts, tables and other visual elements objectively.\n"
    "Rule 3: Do not add any new information and do not hallucinate.\n"
    "Rule 4: Do not interpret anything that is not explicitly visible in the image.\n"
    "Rule 5: Do not use semicolons or any type of dash. Use only periods, commas and question marks.\n"
    "Rule 6: Respond in the same language as the primary text in the image content."
)

# What the vision model is asked when the person typed nothing.
DEFAULT_QUESTION = "Analyze this image."

# Ready-made edit instructions, shown as buttons on the page.
QUICK_EDITS = {
    "white": "Replace the background with plain white, keep the subject unchanged.",
    "sketch": "Redraw the image as a pencil sketch with loose lines.",
    "no_text": "Remove all text and letters from the image, keep everything else.",
    "vivid": "Make the colors stronger and the contrast slightly higher, keep the content.",
}
