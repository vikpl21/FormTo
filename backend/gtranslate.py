import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./translateapi.json"

def translate_text(target, text):
		from google.cloud import translate_v2 as translate
		
		translate_client = translate.Client()
		output = translate_client.translate(
			text,
			target_language=target
		)
		return output
