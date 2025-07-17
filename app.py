#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import random
from datetime import datetime
from flask import Flask, render_template, request
import os
import shutil

# Создаём папку templates, если её нет
if not os.path.exists('templates'):
    os.makedirs('templates')

# Копируем index.html, если его ещё нет в templates
if not os.path.exists('templates/index.html'):
    if os.path.exists('index.html'):
        shutil.copy('index.html', 'templates/index.html')
    else:
        # Если index.html нет рядом с app.py, создаём простой шаблон
        with open('templates/index.html', 'w', encoding='utf-8') as f:
            f.write('<h1>Welcome! index.html не найден.</h1>')

app = Flask(__name__)

class LinkedInJobScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        self.jobs_list = []

    def get_user_requirements(self, keywords, locations):
        """Получение требований пользователя"""
        return {
            'keywords': [kw.strip() for kw in keywords.split(',') if kw.strip()],
            'locations': [loc.strip() for loc in locations.split(',') if loc.strip()],
            'max_pages': 3  # Значение по умолчанию
        }

    def scrape_jobs(self, requirements):

        """Скрапинг вакансий с LinkedIn с фильтрацией по уникальной ссылке"""
        print("\n🔍 НАЧИНАЕМ СКРАПИНГ ВАКАНСИЙ...")

        self.jobs_list = []
    
        for city in requirements['locations']:
            for kw in requirements['keywords']:
                for start in range(0, requirements['max_pages'] * 25, 25):
                    try:
                        kw_encoded = kw.replace(" ", "%20")
                        city_encoded = city.replace(" ", "%20")
                        url = (
                            f'https://www.linkedin.com/jobs/search/?'
                            f'keywords={kw_encoded}&location={city_encoded}&start={start}'
                        )
                        print(f'📄 Страница: {url}')
                        response = requests.get(url, headers=self.headers, timeout=15)
                        soup = BeautifulSoup(response.text, 'html.parser')
    
                        job_cards = soup.find_all('div', class_='base-card')
                        print(f'   ➤ Найдено: {len(job_cards)} вакансий')
    
                        for job in job_cards:
                            job_data = self.extract_job_data(job, kw, city)
                            if job_data:
                                self.jobs_list.append(job_data)
    
                        time.sleep(random.uniform(2, 5))
    
                    except Exception as e:
                        print(f"❌ Ошибка при скрапинге: {e}")
                        time.sleep(10)
    
        # --- Фильтрация дубликатов по ссылке ---
        unique_links = set()
        unique_jobs = []
        for job in self.jobs_list:
            link = job.get('Link')
            if link and link not in unique_links:
                unique_jobs.append(job)
                unique_links.add(link)
        self.jobs_list = unique_jobs
    
        print(f"✅ Всего собрано {len(self.jobs_list)} уникальных вакансий")

        return self.jobs_list

    def extract_job_data(self, job, keyword, city):
        """Извлечение данных о вакансии"""
        try:
            title = job.find('h3', class_='base-search-card__title')
            title = title.text.strip() if title else ''

            company = job.find('h4', class_='base-search-card__subtitle')
            company = company.text.strip() if company else ''

            location = job.find('span', class_='job-search-card__location')
            location = location.text.strip() if location else ''

            link_elem = job.find('a', class_='base-card__full-link')
            link = link_elem['href'] if link_elem else ''

            date_elem = job.find('time', class_='job-search-card__listdate')
            date_posted = date_elem.text.strip() if date_elem else 'Не указано'

            return {
                'Title': title,
                'Company': company,
                'Location': location,
                'Link': link,
                'Keyword': keyword,
                'Search_City': city,
                'Date_Posted': date_posted,
                'Date_Scraped': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"❌ Ошибка извлечения данных: {e}")
            return None

    def fetch_job_descriptions(self):
        """Получение полных описаний вакансий"""
        print("\n📝 ПОЛУЧЕНИЕ ОПИСАНИЙ ВАКАНСИЙ...")
        descriptions = []
        salaries = []

        for i, job in enumerate(self.jobs_list):
            if not job['Link']:
                descriptions.append('Ссылка недоступна')
                salaries.append('Не указано')
                continue

            print(f"{i+1}/{len(self.jobs_list)} | {job['Title'][:50]}...")

            try:
                response = requests.get(job['Link'], headers=self.headers, timeout=12)
                soup = BeautifulSoup(response.text, 'html.parser')

                desc_block = soup.find(
                    'div',
                    {'class': lambda x: x and 'description' in x.lower() if x else False}
                )
                if not desc_block:
                    desc_block = soup.find(
                        'section',
                        {'class': lambda x: x and 'description' in x.lower() if x else False}
                    )

                if desc_block:
                    description = desc_block.get_text(separator=' ', strip=True)
                else:
                    description = 'Описание не найдено'

                salary = self.extract_salary(soup, description)

                descriptions.append(description)
                salaries.append(salary)

                time.sleep(random.uniform(1.5, 4))

            except Exception as e:
                print(f"❌ Ошибка получения описания: {e}")
                descriptions.append('Ошибка загрузки')
                salaries.append('Не указано')

        return descriptions, salaries

    def extract_salary(self, soup, description):
        """Извлечение информации о зарплате"""
        salary_patterns = [
            r'€\s*([0-9]{2,3}[.,]?[0-9]{3})[\\s-]*([0-9]{2,3}[.,]?[0-9]{3})?',
            r'([0-9]{2,3})[.,]?([0-9]{3})\s*€',
            r'salary.*?([0-9]{2,3}[.,]?[0-9]{3})',
            r'gehalt.*?([0-9]{2,3}[.,]?[0-9]{3})',
        ]

        text = description.lower()
        for pattern in salary_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return 'Не указано'

    def analyze_with_ai(self, df, user_prompt, priority_keywords):
        """AI-анализ и приоритизация вакансий"""
        print("\n🤖 AI-АНАЛИЗ И ПРИОРИТИЗАЦИЯ...")

        df['Brief_Description'] = df.apply(self.create_brief_description, axis=1)
        df['Skills_Match'] = df['Description'].apply(
            lambda x: self.calculate_skills_match(x, priority_keywords)
        )
        df['Remote_Work'] = df['Description'].apply(self.detect_remote_work)
        df['Seniority_Level'] = df['Description'].apply(self.detect_seniority)
        df['Language'] = df['Description'].apply(self.detect_language)
        df['Priority'] = df.apply(
            lambda row: self.calculate_priority(row, user_prompt, priority_keywords), axis=1
        )

        df = df.sort_values('Priority')
        return df

    def create_brief_description(self, row):
        """Создание краткого описания вакансии"""
        desc = row['Description'][:300] + "..." if len(row['Description']) > 300 else row['Description']
        return f"{row['Title']} в {row['Company']}, {row['Location']}. {desc}"

    def calculate_skills_match(self, description, priority_keywords):
        """Подсчет соответствия навыков"""
        desc_lower = description.lower()
        matches = sum(1 for keyword in priority_keywords if keyword in desc_lower)
        return f"{matches}/{len(priority_keywords)}"

    def detect_remote_work(self, description):
        """Определение возможности удаленной работы"""
        remote_keywords = [
            'remote', 'home office', 'hybrid', 'remotearbeit', 'homeoffice', 'от дома'
        ]
        desc_lower = description.lower()
        return any(keyword in desc_lower for keyword in remote_keywords)

    def detect_seniority(self, description):
        """Определение уровня позиции"""
        desc_lower = description.lower()
        if any(word in desc_lower for word in ['senior', 'lead', 'principal', 'architect']):
            return 'Senior'
        elif any(word in desc_lower for word in ['junior', 'entry', 'anfänger']):
            return 'Junior'
        elif any(word in desc_lower for word in ['manager', 'head', 'director', 'leitung']):
            return 'Management'
        elif any(word in desc_lower for word in ['intern', 'praktikum', 'werkstudent']):
            return 'Intern/Student'
        else:
            return 'Mid-level'

    def detect_language(self, description):
        """Определение основного языка вакансии"""
        desc_lower = description.lower()
        english_words = ['responsibilities', 'requirements', 'experience', 'skills', 'apply']
        german_words = ['anforderungen', 'verantwortung', 'erfahrung', 'kenntnisse', 'bewerben']

        en_count = sum(1 for word in english_words if word in desc_lower)
        de_count = sum(1 for word in german_words if word in desc_lower)

        if en_count > de_count:
            return 'English'
        elif de_count > en_count:
            return 'German'
        else:
            return 'Mixed'

    def calculate_priority(self, row, user_prompt, priority_keywords):
        """Расчет приоритета вакансии на основе AI-логики"""
        score = 0
        desc_lower = row['Description'].lower()
        title_lower = row['Title'].lower()

        skills_matched = sum(1 for keyword in priority_keywords if keyword in desc_lower)
        score += skills_matched * 10

        title_matches = sum(1 for keyword in priority_keywords if keyword in title_lower)
        score += title_matches * 15

        prompt_words = user_prompt.lower().split()
        prompt_matches = sum(1 for word in prompt_words if len(word) > 3 and word in desc_lower)
        score += prompt_matches * 5

        if row['Remote_Work'] and any(word in user_prompt.lower() for word in ['remote', 'удален', 'дом']):
            score += 20

        if 'Salary' in row and row['Salary'] != 'Не указано':
            score += 10

        if row['Seniority_Level'] == 'Senior' and 'junior' in user_prompt.lower():
            score -= 15
        elif row['Seniority_Level'] == 'Junior' and 'senior' in user_prompt.lower():
            score -= 15

        if score >= 50:
            return 1
        elif score >= 25:
            return 2
        else:
            return 3

    def save_results(self, df):
        """Сохранение результатов"""
        columns_order = [
            'Priority', 'Title', 'Company', 'Location', 'Brief_Description',
            'Skills_Match', 'Salary', 'Remote_Work', 'Seniority_Level',
            'Language', 'Date_Posted', 'Link', 'Description'
        ]

        for col in columns_order:
            if col not in df.columns:
                df[col] = 'Не определено'

        df_ordered = df[columns_order]

        excel_filename = f"linkedin_jobs_ai_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_ordered.to_excel(excel_filename, index=False)

        csv_filename = excel_filename.replace('.xlsx', '.csv')
        df_ordered.to_csv(csv_filename, index=False)

        print(f"\n✅ РЕЗУЛЬТАТЫ СОХРАНЕНЫ:")
        print(f"📊 Excel файл: {excel_filename}")
        print(f"📄 CSV файл: {csv_filename}")
        print(f"📈 Всего проанализировано вакансий: {len(df)}")

        priority_stats = df['Priority'].value_counts().sort_index()
        print(f"\n📊 СТАТИСТИКА ПО ПРИОРИТЕТАМ:")
        for priority, count in priority_stats.items():
            priority_name = {1: 'Высокий', 2: 'Средний', 3: 'Низкий'}.get(priority, 'Неопределен')
            print(f"   Приоритет {priority} ({priority_name}): {count} вакансий")

        return excel_filename, csv_filename

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    scraper = LinkedInJobScraper()
    keywords = request.form['keywords']
    locations = request.form['locations']
    max_pages = int(request.form.get('max_pages', 3))  # Значение по умолчанию 3
    
    requirements = scraper.get_user_requirements(keywords, locations)
    requirements['max_pages'] = max_pages  # Устанавливаем количество страниц

    jobs = scraper.scrape_jobs(requirements)
    if not jobs:
        return "❌ Вакансии не найдены."

    descriptions, salaries = scraper.fetch_job_descriptions()
    df = pd.DataFrame(jobs)
    df['Description'] = descriptions
    df['Salary'] = salaries

    user_prompt = request.form.get('user_prompt', '')
    priority_keywords = [
        kw.strip().lower() for kw in request.form.get('priority_keywords', '').split(',') if kw.strip()
    ]

    df_analyzed = scraper.analyze_with_ai(df, user_prompt, priority_keywords)
    excel_file, csv_file = scraper.save_results(df_analyzed)

    return f"✅ Результаты сохранены в {excel_file} и {csv_file}."

if __name__ == "__main__":
    app.run(debug=True)



# In[ ]:




