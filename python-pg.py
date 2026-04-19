import psycopg2
from psycopg2 import sql
import UDP_Client
from splashscreen import SplashScreen 
from player_entry import entry_terminal
from Countdown_timer import CountdownTimer


# Define connection parameters
connection_params = {
    'dbname': 'photon',
    'user': 'student',
    'password': 'student',
    #'host': 'localhost',
    #'port': '5432'
}

def read_int(prompt: str) -> int:
    while True:
        s = input(prompt).strip()
        if s.isdigit():
            return int(s)
        print("Please enter a numeric equipment id.")


def run_app():
    try:
		
        # connect to server network
        UDP_Client.configure_server()
        print("Using UDP server:", UDP_Client.SERVER_ADDRESS)

        # Connect to PostgreSQL
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()

        conn.commit()

        cursor.close()
        conn.close()

        # Launch GUI using SAME db config
        entry_terminal(connection_params)
        
        

    except Exception as error:
        print(f"Error: {error}")

if __name__ == "__main__":
#  SplashScreen(on_close=run_app, image_path="logo.jpg", duration_ms=3000).show()
    SplashScreen(on_close=run_app,
                image_path="logo.jpg",
                duration_ms=3000).show()
    




