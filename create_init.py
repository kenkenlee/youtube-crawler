import os


# Create __init__.py files for all packages
def create_init_files():
    packages = [
        "app",
        "app/api",
        "app/schemas",
        "app/services",
        "app/tasks"
    ]

    for package in packages:
        init_file = os.path.join(package, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("")
            print(f"Created {init_file}")


if __name__ == "__main__":
    create_init_files()
