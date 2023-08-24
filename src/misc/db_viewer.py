import plyvel

class DatabaseViewer:
    def __init__(self, db_path):
        self.db = plyvel.DB(db_path)

    def view_all(self):
        for key, value in self.db:
            print(f"Key: {key.decode()}, Value: {value.decode()}")

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
