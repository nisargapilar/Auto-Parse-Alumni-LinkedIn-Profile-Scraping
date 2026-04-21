## 🚀 AutoParse System

The AutoParse system enables efficient scraping, storage, and utilization of alumni LinkedIn profiles. It provides a secure dashboard where users authenticate to access features for seamless data management and alumni engagement.

### 🔑 Key Modules

- **Live Profile Parsing**  
  Extracts key details from LinkedIn profile URLs provided by users in real time.

- **Database Access Search**  
  Retrieves previously parsed profiles from Firestore using keyword-based queries.

- **Canara Alumni Scraping Module**  
  Collects selected or bulk LinkedIn profiles and stores them in structured JSON format.

- **Automated Email Outreach**  
  Identifies profiles with valid email addresses and sends automated emails to initiate networking.

### ⚙️ System Workflow

The Live Parsing and Canara Alumni modules collect HTML data from LinkedIn profiles and pass it to the parsing module. This module converts the data into structured JSON and uploads it to Firestore for secure storage and easy retrieval.

Users can search, download JSON files, and automate communication through email outreach. Together, these components create a complete workflow for scraping, parsing, storing, searching, downloading, and communication, making AutoParse a scalable and efficient solution for alumni engagement.

### 📸 System Architecture / Demo

![AutoParse System Architecture](./images/autoparse-diagram.png)
