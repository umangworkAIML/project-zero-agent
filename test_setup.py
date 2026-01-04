from tools import execute_python_file, write_file

print("🛠️ Testing Tools...")

# Test 1: Write a dummy file
print("1. Writing test file...")
print(write_file.invoke({"file_path": "hello.py", "content": "print('Hello from Project Zero!')"}))

# Test 2: Execute that file
print("2. Executing test file...")
print(execute_python_file.invoke({"file_path": "hello.py"}))