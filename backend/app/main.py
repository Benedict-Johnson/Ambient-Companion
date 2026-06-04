from app.llm import generate_response
from app.tts import speak
from app.stt import listen


def main():

    print("Freya Voice Online.")

    while True:

        user_input = listen()

        print(f"\nYou: {user_input}")

        response = generate_response(user_input)

        print(f"\nFreya: {response}")

        speak(response)


if __name__ == "__main__":
    main()