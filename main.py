import tweepy
import random
import os
import json
import requests

# API credentials from GitHub Secrets
API_KEY = os.environ["X_API_KEY"]
API_SECRET = os.environ["X_API_SECRET"]
ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]
HF_TOKEN = os.environ["HF_TOKEN"]
PEXELS_KEY = os.environ["PEXELS_KEY"]

# Hugging Face API
HF_API_URL = "https://api-inference.huggingface.co/models/mixtral-8x7b-instruct-v0.1"

# Authenticate X API
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Topics and emojis
topics = ["self_improvement", "studying", "fun_facts", "ai_tools", "macos_tips"]
emojis = {
    "self_improvement": "🌱",
    "studying": "📚",
    "fun_facts": "✨",
    "ai_tools": "💡",
    "macos_tips": "🍎"
}

# Track subtopics
HISTORY_FILE = "history.txt"

def load_history():
    default_history = {topic: [] for topic in topics}
    if not os.path.exists(HISTORY_FILE):
        print(f"{HISTORY_FILE} not found, initializing with default")
        return default_history
    with open(HISTORY_FILE, "r") as f:
        content = f.read().strip()
        if not content:
            print(f"{HISTORY_FILE} is empty, initializing with default")
            return default_history
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {HISTORY_FILE}: {e}, resetting to default")
            return default_history

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def query_hf(prompt):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": f"[INST] {prompt} [/INST]",
        "parameters": {"max_new_tokens": 300, "temperature": 0.7}
    }
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            text = response.json()[0]["generated_text"].split("[/INST]")[-1].strip()
            return text
        print(f"HF API error: {response.status_code}, {response.text}")
        return None
    except Exception as e:
        print(f"HF query failed: {e}")
        return None

def fetch_pexels_image(query):
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    headers = {"Authorization": PEXELS_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            img_url = response.json()["photos"][0]["src"]["medium"]
            img_data = requests.get(img_url).content
            img_path = f"temp_{random.randint(1000, 9999)}.jpg"
            with open(img_path, "wb") as f:
                f.write(img_data)
            return img_path
        print(f"Pexels API error: {response.status_code}")
        return None
    except Exception as e:
        print(f"Pexels fetch failed: {e}")
        return None

def generate_content(topic):
    print(f"Generating content for topic: {topic}")
    history = load_history()
    used_subtopics = history.get(topic, [])

    # Generate subtopic
    for _ in range(3):
        prompt = (
            f"Suggest a unique, specific subtopic for {topic.replace('_', ' ')}. "
            f"Avoid: {', '.join(used_subtopics) or 'none'}. "
            "Output only the subtopic name, <30 chars."
        )
        subtopic = query_hf(prompt)
        print(f"Generated subtopic attempt: {subtopic}")
        if subtopic and subtopic not in used_subtopics and len(subtopic) < 30:
            break
    else:
        subtopic = used_subtopics[-1] if used_subtopics else f"{topic}_general"
        print(f"Subtopic fallback: {subtopic}")

    # Generate thread
    prompt = (
        f"Write a 3-tweet thread on {subtopic} for {topic.replace('_', ' ')}. "
        "Each tweet <280 chars, based on verified info, 1-2 hashtags. "
        f"Main tweet starts with 🧵, parts use 1️⃣, 2️⃣, 3️⃣. Include {emojis[topic]}. "
        "Separate tweets with ||. No speculation."
    )
    thread_text = query_hf(prompt)
    if not thread_text:
        print("Thread generation failed")
        return None
    thread_parts = [p.strip() for p in thread_text.split("||")]
    print(f"Thread parts: {thread_parts}")
    if len(thread_parts) != 4:  # Main + 3
        print(f"Invalid thread format: {thread_parts}")
        return None

    # Generate image keywords
    prompt = (
        f"Suggest 3 image keywords for {subtopic} ({topic.replace('_', ' ')}). "
        "Output: keyword1,keyword2,keyword3"
    )
    keywords = query_hf(prompt) or f"{topic},photo,image"
    keywords = [k.strip() for k in keywords.split(",")][:3]
    print(f"Image keywords: {keywords}")

    # Update history
    used_subtopics.append(subtopic)
    history[topic] = used_subtopics[-10:]
    save_history(history)

    return {
        "main_tweet": thread_parts[0],
        "thread": thread_parts[1:],
        "image_keywords": keywords,
        "topic": topic,
        "subtopic": subtopic
    }

def post_thread():
    print("Starting post_thread")
    # Load or initialize topic index
    index_file = "topic_index.txt"
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            topic_index = int(f.read().strip())
    else:
        topic_index = 0
    print(f"Topic index: {topic_index}")

    topic = topics[topic_index]
    topic_index = (topic_index + 1) % len(topics)

    post = generate_content(topic)
    if not post or any(len(t) > 280 for t in [post["main_tweet"]] + post["thread"]):
        print("Invalid content, skipping...")
        return

    try:
        # Fetch images
        media_ids = []
        auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)

        for i in range(4):  # Main + 3 tweets
            keyword = post["image_keywords"][i % len(post["image_keywords"])]
            img_path = fetch_pexels_image(keyword)
            print(f"Image fetch for {keyword}: {img_path}")
            if img_path and os.path.exists(img_path):
                media = api.media_upload(img_path)
                media_ids.append(media.media_id)
                os.remove(img_path)
            else:
                media_ids.append(None)
                print(f"Image fetch failed for keyword: {keyword}")

        # Post main tweet
        response = client.create_tweet(
            text=post["main_tweet"],
            media_ids=[media_ids[0]] if media_ids[0] else None
        )
        tweet_id = response.data["id"]
        print(f"Posted main: {post['main_tweet']} (Subtopic: {post['subtopic']})")

        # Post thread
        last_tweet_id = tweet_id
        for i, part in enumerate(post["thread"]):
            media_id = media_ids[i + 1] if i + 1 < len(media_ids) else None
            response = client.create_tweet(
                text=part,
                in_reply_to_tweet_id=last_tweet_id,
                media_ids=[media_id] if media_id else None
            )
            last_tweet_id = response.data["id"]
            print(f"Posted thread part: {part}")

        # Save topic index
        print(f"Saving topic index: {topic_index}")
        with open(index_file, "w") as f:
            f.write(str(topic_index))

    except Exception as e:
        print(f"Posting failed: {e}")

if __name__ == "__main__":
    post_thread()
