# 🧰 CallFlow Markdown Tool

Convert Microsoft Call Flow Visualizer `.htm/.html` exports (with Mermaid diagrams) into clean, structured Markdown documents.

---

## ✅ Usage (Windows)

1. Install Python from [https://python.org](https://python.org)
2. Open Command Prompt
3. Run:
    ```bash
    pip install beautifulsoup4
    cd C:\Mermaid_to_Markdown_CallFlow_Tool
    python batch_callflow_to_md.py flows
    ```
### 💡 Tips for Windows
> You can drag and drop the .py file into a terminal window after typing python to auto-fill the path.


> If Python isn't recognized, make sure it was added to PATH, or run it via:
> ```arduino
>"C:\Path\To\Python\python.exe" batch_callflow_to_md.py .
>```


## 🐧 Usage (Linux/Mac)

   ```bash
    pip3 install beautifulsoup4
    cd Mermaid_to_Markdown_CallFlow_Tool
    python3 batch_callflow_to_md.py flows
  ```

## Functions 
Users should ensure 'flows' folder/directory should be placed in the same folder as this script. This folder/directory should have all the existing Mermaid documents (often created with M365 Call Flow Visualizer).

**Limit # of files processed:** 
```bash 
 python batch_callflow_to_md.py flows --limit 5
```

**Debug Mode**
Run it with debug mode:
```
python batch_callflow_to_md.py myfolder/ --debug
```