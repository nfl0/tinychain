import plyvel
import json

class DatabaseViewer:
    def __init__(self, db_path):
        self.db = plyvel.DB(db_path)

    def format_entry(self, key, value):
        return f"Key: {key.decode()}\nValue: {self.beautify_json(value.decode())}\n{'-'*40}"

    def beautify_json(self, value):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, indent=4, sort_keys=True)
        except json.JSONDecodeError:
            return value

    def view_all(self):
        for key, value in self.db:
            print(self.format_entry(key, value))

    def close(self):
        self.db.close()

def main():
    db_path = input("Enter the path to the database directory: ")
    db_viewer = DatabaseViewer(db_path)
    
    while True:
        print("\nOptions:")
        print("1. View all data")
        print("2. Exit")

        choice = input("Select an option: ")

        if choice == "1":
            db_viewer.view_all()
        elif choice == "2":
            db_viewer.close()
            break
        else:
            print("Invalid choice. Please select a valid option.")

if __name__ == "__main__":
    main()
