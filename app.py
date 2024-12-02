from flask import Flask, jsonify, render_template, request, url_for
from flask_cors import CORS 
import requests
import json

app = Flask(__name__)

CORS(app)

def load_recipes(file_path):
    """
    Load recipe data from a JSON file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

recipes_data = load_recipes("static/recipes.json")

#Return list of recipes that contain the given ingredient
def recommend_recipes_by_ingredient(ingredient, recipes_data):
    matching_recipes = []
    for recipe in recipes_data:
        if any(ingredient in ing for ing in recipe["ingredients"]):
            matching_recipes.append({
                "id": recipe["id"],
                "title": recipe["name"],
                "image_url": recipe.get("image_url")
            })
    return matching_recipes[:3]

## Get recipe details
def get_recipe_by_id(recipe_id, recipes_data):
    for recipe in recipes_data:
        if recipe["id"] == recipe_id:
            return recipe
    return None

# Translate text to Japanese by DeepL API
def translate_to_japanese(text, source_language="zh"):
    try:
        url = "https://api-free.deepl.com/v2/translate"
        params = {
            "auth_key": "043fd986-7b73-477e-a52a-de26446c5c71:fx", 
            "text": text,
            "target_lang": "JA"
        }
        response = requests.post(url, data=params)
        response.raise_for_status() # to check if the request was successful
        translated_text = response.json()["translations"][0]["text"]
        
        # If the source language is Chinese, add a note about the source
        if source_language == "zh":
            translated_text += "\n\n本内容は中国語版Wikipediaから引用され、自動的に日本語に翻訳されました。"

        return translated_text
    except Exception as e:
        return f"翻訳サービスは現在利用できません。後ほど再試行してください。"

# Fetch information from Chinese Wikipedia and translate the description to Japanese
def fetch_japanese_wikipedia(title):
    url = "https://zh.wikipedia.org/w/api.php" 
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts|pageimages",
        "exintro": True,
        "explaintext": True,
        "pithumbsize": 500,
        "redirects": True
    }
    response = requests.get(url, params=params)
    data = response.json()

   # Get page data (the first page in the response)
    page = list(data['query']['pages'].values())[0]
    if "missing" in page:
        # fuzzy search
        return {
            "error": "関連ページが見つかりませんでした。",
            "suggestions": search_wikipedia(title)
        }
    
    # If the page is found, get the description and translate it to Japanese
    description = page.get("extract", "説明はありません。")
    translated_description = translate_to_japanese(description, source_language="zh")
    
    return {
        "title": page.get("title"),
        "description": translated_description,
        "image_url": page.get("thumbnail", {}).get("source")
    }

#  Perform a fuzzy search on Wikipedia and return the list of matching titles.
def search_wikipedia(query):
    url = "https://zh.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json"
    }
    response = requests.get(url, params=params)
    data = response.json()

    # Extract search results (titles of matching pages)
    return [item["title"] for item in data.get("query", {}).get("search", [])]

@app.route("/", methods=["GET", "POST"])
def index():
    # Get the ingredient input from either GET or POST request
    user_input = request.args.get("ingredient") or request.form.get("ingredient")
    if not user_input:
        return render_template("index.html", error=None, result=None)

    try:
        # Fetch Wikipedia data based on the ingredient
        wikipedia_data = fetch_japanese_wikipedia(user_input)

        # If there is an error or fuzzy search suggestions, return those
        if "error" in wikipedia_data:
            return render_template(
                "index.html",
                error=wikipedia_data["error"],
                suggestions=wikipedia_data.get("suggestions", []),
                result=None,
                no_recipes=False
            )

        # Recommend recipes based on the ingredient
        recommended_recipes = recommend_recipes_by_ingredient(user_input, recipes_data)

        if not recommended_recipes:  # If no recipes are found
            no_recipes = True
            wikipedia_data["recipes"] = []
        else:
            no_recipes = False
            wikipedia_data["recipes"] = recommended_recipes

        # Render the result on the index page
        return render_template("index.html", result=wikipedia_data, error=None, no_recipes=no_recipes)

    except Exception as e:
        # Handle any exceptions and display an error message
        return render_template("index.html", error=f"An error occurred: {e}", result=None, no_recipes=False)
    
@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipe = get_recipe_by_id(recipe_id, recipes_data)
    if recipe:
        # Get the previous ingredient
        previous_ingredient = request.args.get('ingredient', '') 
        return render_template("recipe_detail.html", recipe=recipe, previous_ingredient=previous_ingredient)
    else:
        return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=True)