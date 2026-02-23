import asyncio
import sys
import os

# Add the backend to path so we can import from api
sys.path.append(os.path.abspath('SmartIntern-backend'))

from api.ai_utils import analyze_resume_match
from dotenv import load_dotenv
load_dotenv('SmartIntern-backend/.env')

job_description = """We are seeking a detail-oriented and technically strong QA Engineer with hands-on experience in web and full-stack application development. The ideal candidate should have practical exposure to testing responsive web applications built using HTML, CSS, JavaScript, and MERN stack technologies, along with validating REST APIs, authentication systems, and database operations (MongoDB/MySQL). The role involves performing functional, regression, UI, API, and cross-browser testing, identifying edge cases, debugging performance issues, and ensuring reliability of AI-integrated features such as chatbot APIs. A strong understanding of SDLC, STLC, cloud deployment environments, and Linux systems is preferred. The candidate should possess excellent problem-solving skills, attention to detail, and the ability to collaborate with development teams to deliver secure, scalable, and high-quality software solutions."""

resume_text = """Shashank Singh 
Linkedin: https://www.linkedin.com/in/shashank-singh29  Email: shashanksingh9048@gmail.com 
Github: github.com/Shashank9048                            Mobile: +91-9630023003 
SKILLS 
 
• Languages: Java, C++, JavaScript, Bash, Shell Scripting. 
• Frameworks: HTML and CSS 
• Tools/Platforms: MySQL 
• Cloud Services: AWS, Apache, Google Cloud. 
• Operating System: Linux(RedHat, Ubuntu), Windows. 
• Soft Skills: Problem-Solving , Team Player, Project Management, Adaptability 
WORK EXPERIENCE 
 
• WowwDecors & Events:                Oct 2025 - Nov 2025 
Freelance Web-Developer 
Collaborated with a team to design and develop a fully responsive and interactive website for a US-based event management 
startup. The website was built to showcase services, highlight previous projects, and handle client bookings efficiently. 
Implemented dynamic image galleries, an event booking form, and client testimonial sections to improve user engagement. 
Created a clean, modern, and intuitive interface that reflects the brand’s creativity and professionalism, while ensuring full cross-
browser compatibility and seamless performance across all devices. 
Tech: HTML, Tailwind CSS, JavaScript, jQuery. 
 
• TheMudrak - Sustainable and Eco-Friendly Printing & Packaging Store Website: 
Freelance Web-Developer                Jan 2025 - Mar 2025 
Developed a responsive website for TheMudrak, a sustainable and environment-friendly printing and packaging brand. 
Designed the front-end using HTML, CSS, and JavaScript, and implemented dynamic features using WordPress for ease of 
content management.Created an intuitive UI/UX to showcase eco-friendly products, enhancing user engagement. 
Ensured complete mobile responsiveness and fast loading times. 
Tech: HTML, CSS, JavaScript, WordPress. 
Website:  https://themudrak.com/ 
 
PROJECTS 
 
• TechConnect3003:                  Jul 2025 – Aug 2025 
Designed and developed a full-stack web application using the MERN stack (MongoDB, Express.js, React.js, Node.js) to 
connect users on a unified platform for technical interaction and collaboration. Built a modern, responsive frontend with React and 
implemented a robust backend with Node.js and Express for handling APIs, authentication, and data management. Integrated 
MongoDB for efficient storage and retrieval of user and application data. The project focuses on performance, scalability, and a 
smooth user experience, demonstrating strong full-stack development skills and real-world application architecture. 
Tech: MongoDB, Express.js, React.js, Node.js, JavaScript, REST APIs, Authentication, Responsive UI. 
 
• Smart Portfolio:                   Jul 2025 - Jul 2025 
Created and deployed a modern, fully responsive personal portfolio website to showcase my skills, projects, and professional 
information. The site features clean navigation, visually engaging layout, and sections that highlight my technical expertise and 
project work. Integrated AI-assisted enhancements using Gemini AI to improve content presentation and user engagement. 
Hosted the live site on Netlify and published the source code publicly on GitHub, demonstrating my ability to build, document, and 
maintain a real-world web application. 
Tech: HTML, CSS, JavaScript/TypeScript, Tailwind CSS, AI-assisted content (Gemini AI). 
Website: https://shashanksmartportfolio.netlify.app/ 
 
• Directory Management System - Smart File Organization and Duplicate Finder:                   Apr 2025 - Apr 2025       
Built a GUI-based Directory Management System using Python and Tkinter. 
Automatically categorizes files into folders based on file types (Images, Documents, Videos, etc.). 
Implements duplicate file detection using MD5 hashing and provides options to organize, preview, and undo file operations. 
Built a user-friendly interface with progress bars and scanning previews for large directories. 
Tech: Python, Tkinter, OS Module, Hashlib, Magic (MIME Type Detection), Multithreading. 
 
• FitLife Planner Pro - AI-Integrated Fitness Planner Website:                   Apr 2025 - Apr 2025 
Built FitLife Planner Pro, a fitness planning website featuring an AI-powered chatbot assistant. 
Developed a full planner system for workouts, meals, and progress tracking using HTML, CSS, and JavaScript. 
Integrated Google’s Gemini API for the chatbot to answer fitness-related queries dynamically. 
Designed a clean, mobile-responsive dashboard UI and animated chat interactions for better engagement. 
Tech: HTML, CSS, JavaScript, Gemini API (Chatbot), Netlify Deployment. 
 
• SkillSeed:                  Nov 2024– Dec 2024 
Developed SkillSeed, an educational and skill-focused web platform designed to provide users with access to structured courses 
and learning content. Built a clean, modern, and responsive user interface that allows learners to easily explore different skill 
categories, navigate courses, and interact with the site’s features. Integrated AI-enhanced elements (such as chat assistance or 
intelligent content hints) to elevate the learning experience and support user engagement. The project is fully open-source and 
showcases practical implementation of web development fundamentals along with polished design and client-facing UI features. 
Tech: HTML, CSS, JavaScript. 
   TRAINING 
 
 
• InternsVeda Edutech Pvt. Ltd.:                Dec 2024 - Jan 2025  
Cloud Computing Intern & Trainee 
Completed a combined training and internship program in cloud computing, gaining hands-on experience with virtualization, 
infrastructure, and deployment.Collaborated on real-world cloud projects, optimizing performance, scalability, and security using 
industry best practices. 
        Skills Acquired: Cloud Computing, Virtualization, Infrastructure Management, Deployment, Security 
 
 
CERTIFICATES 
 
• Internship and Training in Cloud Computing with InternsVeda                                                                                       Nov 2024-Jan 2025 
• Certified in MERN Stack Development from CipherSchools                                                                                                Jun 2025-Jul 2025 
ACHIEVEMENTS 
• LeetCode 100 Days Badge:             Jan 2025 
Completed the 100 Days of LeetCode challenge, demonstrating persistence and consistent practice in data structures and 
algorithms. 
 
• Extracurricular Involvement and Leadership Roles:   
     • Dehradun Science Exhibition Winner: 
       Won 1st prize in city-level science exhibition held in Dehradun. 
     • President – Club Palo Alto – The Tall Tree: 
       Organized and led several college events as the club president, demonstrating strong leadership and event management. 
 
EDUCATION 
 
• Lovely Professional University      Phagwara, Punjab    Bachelor of Technology - Computer Science and Engineering CGPA:7.52           Oct  2023 – May 2027 
• Shivalik Academy                                                                                                                             Dehradun, Uttarakhand           Intermediate  Percentage:81.6%        Apr 2022 - Mar 2023 
• Venus Public School              Gwalior, MP           Secondary Education  Percentage: 87.6%       Apr 2 020 - Mar 2021"""

async def main():
    result = await analyze_resume_match(resume_text, job_description)
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
