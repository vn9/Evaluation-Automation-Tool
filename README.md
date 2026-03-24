# Evaluation-Automation-Tool
A Python-based GUI that processes raw data (textbox), then automatically fills and generates fillable PDF documents with the processed results. Ideal for automating form generation, reporting, and document workflows.

The application allows users to:
<ul>
  <li> Paste Helpdesk job data</li>
  <li> Extract and format information </li>
  <li> Select repair items or inspection items </li>
  <li> Generate folders</li>
  <li> Fill PDF forms automatically</li>
  <li> Print the generated documents</li>
</ul>

<h4>Executable File</h4>
<img src="./images/execution_program.png" alt="gui" width="100"/>
<h4>Launch App</h4>
<img src="./images/GUI.png" alt="gui" width="450"/>
<h4>Extractring Data</h4>
<img src="./images/demo_extracting.png" alt="gui" width="450"/>
<h4>Popup Items</h4>
<img src="./images/demo_popup_items.png" alt="gui" width="600"/>
<h4>Popup Repairs</h4>
<img src="./images/demo_popup_repairs.png" alt="gui" width="600"/>
<h4>Processed popups</h4>
<img src="./images/demo_gui_after.png" alt="gui" width="450"/>
<h4>Generated products</h4>
<img src="./images/demo_processed_products.png" alt="gui" width="400"/>
<h4>Filled Evaluation PDF</h4>
<img src="./images/demo_pdf_evaluation.png" alt="gui" width="450"/>
<h4>Filled Final PDF</h4>
<img src="./images/demo_pdf_final.png" alt="gui" width="450"/>


# Test Coverage
This project includes structured test coverage across:
<ul>
  <li>UI Test Cases</li> 
  <li>Backend Test Cases</li>
  <li>Regression Test Cases</li>
</ul>

See full test plan: [Test Plan](TEST_PLAN.md)

Test Case Dashboard

A web-based dashboard to visualize UI, Backend, and Regression test cases.

[![Live Demo](https://img.shields.io/badge/Live-Demo-green)](https://vn9.github.io/Evaluation-Automation-Tool/)

# Install dependencies
pip install -r requirements.txt

# Run the application
python main_eval_final.py
