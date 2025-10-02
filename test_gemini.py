from google import genai

client = genai.Client(api_key="AIzaSyAtqJe99Ch84hfYfNCDDq6fBoTuG8siYao")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Are you Gemini AI? Yes or no?"
)
print(response.text)