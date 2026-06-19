import requests
from bs4 import BeautifulSoup
import re
import json
import asyncio
from .db_saver import save_events_to_db
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
from datetime import datetime
from .db_saver import save_events_to_db


def detect_category(title: str) -> str:
    """Определяет категорию по названию события"""
    if not title:
        return 'Событие'
    
    CATEGORY_WORDS = {
        'Спектакль': 'Спектакли',
        'Концерт': 'Концерты',
        'Кино': 'Кино',
        'Фильм': 'Кино',
        'Выставка': 'Выставки',
        'Фестиваль': 'Фестивали',
        'Квест': 'Квесты',
        'Обучение': 'Обучение',
        'Спорт': 'Спорт',
        'Детский': 'Детская афиша',
        'Детская': 'Детская афиша',
        'Вечеринка': 'Вечеринки',
        'Мастер-класс': 'Обучение',
        'Курс': 'Обучение',
        'Шоу': 'События',
        'Праздник': 'События',
        'Гала-концерт': 'Концерты'
    }
    
    for key, value in CATEGORY_WORDS.items():
        if key in title:
            return value
    
    first_word = title.split()[0] if title else ''
    if first_word.startswith('"') or first_word.startswith('«'):
        first_word = first_word[1:]
    if first_word.endswith('"') or first_word.endswith('»'):
        first_word = first_word[:-1]
    
    if first_word in CATEGORY_WORDS:
        return CATEGORY_WORDS[first_word]
    
    return 'Событие'


def extract_price_range(price_text: str) -> Tuple[Optional[int], Optional[int]]:
    if not price_text:
        return None, None

    clean = re.sub(r'[руб\s]+', '', price_text.lower())
    clean = re.sub(r'от', '', clean)
    clean = re.sub(r'до', '-', clean)

    numbers = re.findall(r'\d+', clean)
    if not numbers:
        return None, None

    prices = [int(n) for n in numbers]

    if len(prices) == 1:
        return prices[0], prices[0]
    else:
        return min(prices), max(prices)


def normalize_date(date_str: str) -> Optional[str]:
    if not date_str:
        return None

    current_year = datetime.now().year

    patterns = [
        (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
        (r'(\d{2})\.(\d{2})\.(\d{4})', '%d.%m.%Y'),
        (r'(\d{2})\.(\d{2})', '%d.%m'),
        (r'(\d{1,2})\s+(\w+)', '%d %m'),
    ]

    months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }

    for pattern, fmt in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                if fmt == '%d %m':
                    day = int(match.group(1))
                    month_name = match.group(2).lower()
                    if month_name in months:
                        month = months[month_name]
                        return f"{current_year}-{month:02d}-{day:02d}"
                elif fmt == '%d.%m':
                    day, month = match.groups()
                    return f"{current_year}-{month}-{day}"
                else:
                    date_obj = datetime.strptime(match.group(0), fmt)
                    return date_obj.strftime('%Y-%m-%d')
            except:
                continue

    return None


def parse_event_detail(event_url: str) -> Dict[str, any]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(event_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error loading {event_url}: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    event_data = {}

    match = re.search(r'/(\d+)-', event_url)
    if match:
        event_data['id'] = match.group(1)

    name_elem = soup.find(itemprop="name")
    if name_elem:
        event_data['название'] = name_elem.get_text(strip=True)

    desc_elem = soup.find(itemprop="description")
    if desc_elem:
        desc_text = desc_elem.get_text(separator='\n', strip=True)
        p_tags = desc_elem.find_all('p')
        if p_tags:
            full_desc = '\n'.join([p.get_text(strip=True) for p in p_tags])
            event_data['описание'] = full_desc if len(full_desc) > len(desc_text) else desc_text
        else:
            event_data['описание'] = desc_text

    if not event_data.get('описание') or len(event_data.get('описание', '')) < 100:
        desc_sections = soup.select('.b-afisha-event__description, .event-description, .b-ps-content')
        for section in desc_sections:
            text = section.get_text(separator='\n', strip=True)
            if len(text) > len(event_data.get('описание', '')):
                event_data['описание'] = text

    img_elem = soup.find(itemprop="image")
    if img_elem and img_elem.get('src'):
        event_data['постер'] = img_elem.get('src')
    else:
        poster_img = soup.select_one('.b-afisha-event__image')
        if poster_img and poster_img.get('src'):
            event_data['постер'] = poster_img.get('src')

    features = {}
    desc_table = soup.select_one('.b-ps-features')
    if desc_table:
        items = desc_table.select('li')
        for item in items:
            name_span = item.select_one('.b-afisha_cinema_description_table_name')
            desc_span = item.select_one('.b-afisha_cinema_description_table_desc')
            if name_span and desc_span:
                key = name_span.get_text(strip=True).rstrip(':')
                desc_text = desc_span.get_text(strip=True)

                if 'Возрастное ограничение' in key:
                    event_data['возраст'] = desc_text

                links = desc_span.find_all('a')
                if links:
                    link_texts = [link.get_text(strip=True) for link in links]
                    desc_text = ', '.join(link_texts)
                features[key] = desc_text

    if not event_data.get('возраст'):
        age_elem = soup.find('span', string=re.compile(r'Возрастное ограничение'))
        if age_elem:
            parent = age_elem.parent
            if parent:
                age_span = parent.select_one('.b-afisha_cinema_description_table_desc')
                if age_span:
                    event_data['возраст'] = age_span.get_text(strip=True)

    schedule = []
    schedule_items = soup.select('.schedule__item')
    all_prices = []
    all_dates = []
    all_places = []

    for item in schedule_items:
        day_elem = item.select_one('.schedule__day')
        if not day_elem:
            continue

        day_info = {}

        meta_tag = day_elem.find('meta')
        if meta_tag and meta_tag.get('content'):
            date_str = meta_tag.get('content')
            day_info['дата'] = normalize_date(date_str)
            if day_info['дата']:
                all_dates.append(day_info['дата'])

        day_text = day_elem.get_text(strip=True)
        day_info['текст_даты'] = day_text

        places = []
        place_elem = item.select_one('.schedule__place')
        if place_elem:
            place_name_elem = place_elem.select_one('.schedule__place-link')
            place_name = place_name_elem.get_text(strip=True) if place_name_elem else ''
            place_address_elem = place_elem.select_one('.text-black-light')
            place_address = place_address_elem.get_text(strip=True) if place_address_elem else ''

            if place_name:
                all_places.append(place_name)

            seances = []
            seance_items = item.select('.schedule__seance')
            for seance in seance_items:
                seance_data = {}
                time_link = seance.select_one('.schedule__seance-time')
                if time_link:
                    seance_data['время'] = time_link.get_text(strip=True)
                    seance_data['ссылка_билет'] = time_link.get('href', '')

                price_span = seance.select_one('.seance-price')
                if price_span:
                    price_text = price_span.get_text(strip=True)
                    seance_data['цена'] = price_text
                    price_min, price_max = extract_price_range(price_text)
                    if price_min:
                        all_prices.append(price_min)
                    if price_max:
                        all_prices.append(price_max)

                seances.append(seance_data)

            places.append({
                'название': place_name,
                'адрес': place_address,
                'сеансы': seances
            })

        day_info['места'] = places
        schedule.append(day_info)

    if all_dates:
        all_dates = sorted([d for d in all_dates if d])
        if all_dates:
            event_data['дата_начала'] = all_dates[0]
            if len(all_dates) > 1:
                event_data['дата_конца'] = all_dates[-1]
            else:
                event_data['дата_конца'] = all_dates[0]

    if all_prices:
        event_data['цена_мин'] = min(all_prices)
        event_data['цена_макс'] = max(all_prices)

    if all_places:
        event_data['место'] = all_places[0]

    if not event_data.get('раздел') and event_data.get('название'):
        event_data['раздел'] = detect_category(event_data['название'])
    elif event_data.get('название') and event_data.get('раздел') in [None, '']:
        event_data['раздел'] = detect_category(event_data['название'])

    event_data['расписание'] = schedule

    return event_data

def parse_main_page(city_name: str, city_url: str) -> List[Dict[str, any]]:
    base_url = "https://afisha.relax.by"
    full_url = f"{base_url}{city_url}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(full_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error loading {full_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    events = []
    seen_urls = set()

    selectors = [
        'ul.afishaSlider__list_main > li',
        '.afishaSlider__item',
        '.b-afisha_blocks-strap_item',
        '.b-afisha_blocks-movies_item'
    ]

    event_items = []
    for selector in selectors:
        items = soup.select(selector)
        if items:
            event_items = items
            break

    if not event_items:
        links = soup.select('a[href*="/kino/"], a[href*="/theatre/"], a[href*="/conserts/"], a[href*="/event/"]')
        for link in links:
            href = link.get('href')
            if href and 'afisha.relax.by' in href and href not in seen_urls:
                seen_urls.add(href)
                event_data = {
                    'ссылка': href,
                    'название': link.get_text(strip=True) or 'Без названия'
                }
                events.append(event_data)

        print(f"  Found links: {len(events)}")
        return events

    for item in event_items:
        link_elem = item.find('a', class_='b-afisha_blocks-strap_item_lnk') or item.find('a')
        if not link_elem:
            continue

        href = link_elem.get('href', '')
        if not href:
            continue

        if href.startswith('http'):
            event_url = href
        else:
            event_url = base_url + href

        if event_url in seen_urls:
            continue
        seen_urls.add(event_url)

        event_data = {
            'ссылка': event_url,
            'id': link_elem.get('data-id', ''),
            'название': None,
            'раздел': None,
            'город': city_name
        }

        title_elem = item.find('a', class_='b-afisha_blocks-strap_item_lnk_txt')
        if title_elem:
            event_data['название'] = title_elem.get_text(strip=True)

        event_data['раздел'] = link_elem.get('data-schema-title', '')

        img_elem = item.find('img')
        if img_elem:
            poster_url = img_elem.get('src') or img_elem.get('data-src')
            if poster_url:
                event_data['постер'] = poster_url

        date_span = item.find('span', class_='b-afisha-layout_maldives_strap_date')
        if date_span:
            date_text = date_span.get_text(strip=True)
            dates = re.findall(r'(\d{1,2}\s+[а-я]+|\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})', date_text)
            if dates:
                normalized = normalize_date(dates[0])
                if normalized:
                    event_data['дата_начала'] = normalized

        events.append(event_data)

    print(f"  Found events: {len(events)}")
    return events


def parse_rubric_schedule(city_name: str, rubric_url: str) -> List[Dict[str, any]]:
    base_url = "https://afisha.relax.by"
    full_url = f"{base_url}{rubric_url}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(full_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error loading {full_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    events = []
    seen_ids = set()
    seen_urls = set()

    schedule_lists = soup.select('.schedule__list')

    for schedule_list in schedule_lists:
        date_header = schedule_list.select_one('h5')
        current_date = ''
        if date_header:
            current_date = date_header.get_text(strip=True)

        items = schedule_list.select('.schedule__table--movie__item')
        if not items:
            items = schedule_list.select('.schedule__item')

        for item in items:
            event_data = {
                'город': city_name,
                'источник': 'расписание'
            }

            event_link = item.select_one('.js-schedule__event-link')
            if not event_link:
                event_link = item.select_one('a[href*="/kino/"], a[href*="/theatre/"], a[href*="/conserts/"]')

            if event_link:
                href = event_link.get('href', '')
                if href:
                    if href.startswith('http'):
                        event_url = href
                    else:
                        event_url = base_url + href

                    if event_url not in seen_urls:
                        seen_urls.add(event_url)
                        event_data['ссылка'] = event_url

                event_data['название'] = event_link.get_text(strip=True)
                event_data['id'] = event_link.get('data-id', '')

                if event_data['id'] and event_data['id'] in seen_ids:
                    continue
                if event_data['id']:
                    seen_ids.add(event_data['id'])

            place_link = item.select_one('.schedule__place-link')
            if place_link:
                event_data['место'] = place_link.get_text(strip=True)

            if current_date:
                event_data['дата_начала'] = normalize_date(current_date)
            else:
                date_elem = item.select_one('.schedule__day')
                if date_elem:
                    meta_tag = date_elem.find('meta')
                    if meta_tag and meta_tag.get('content'):
                        event_data['дата_начала'] = normalize_date(meta_tag.get('content'))

            price_span = item.select_one('.seance-price')
            if price_span:
                price_text = price_span.get_text(strip=True)
                price_min, price_max = extract_price_range(price_text)
                if price_min:
                    event_data['цена_мин'] = price_min
                if price_max:
                    event_data['цена_макс'] = price_max

            time_link = item.select_one('.schedule__seance-time')
            if time_link:
                event_data['время'] = time_link.get_text(strip=True)
                event_data['ссылка_билет'] = time_link.get('href', '')

            if event_data.get('название') or event_data.get('id'):
                events.append(event_data)

    print(f"  Found in schedule: {len(events)}")
    return events


def parse_all_cities(cities: Dict[str, str]) -> List[Dict[str, any]]:
    all_events = []
    seen_ids = set()
    seen_urls = set()

    rubrics = [
        {'name': 'kino', 'path': '/kino/'},
        {'name': 'conserts', 'path': '/conserts/'},
        {'name': 'theatre', 'path': '/theatre/'},
        {'name': 'event', 'path': '/event/'},
        {'name': 'expo', 'path': '/expo/'},
        {'name': 'kids', 'path': '/kids/'},
        {'name': 'clubs', 'path': '/clubs/'},
        {'name': 'stand-up', 'path': '/stand-up/'},
        {'name': 'education', 'path': '/education/'},
        {'name': 'sport', 'path': '/sport/'},
        {'name': 'festivali', 'path': '/festivali/'},
        {'name': 'quest', 'path': '/quest/'}
    ]

    for city_name, city_path in cities.items():
        print(f"\n{'='*60}")
        print(f"Parsing city: {city_name}")
        print(f"{'='*60}")

        city_events = []

        print("\n  Parsing main page...")
        main_events = parse_main_page(city_name, city_path)
        print(f"    Found on main: {len(main_events)}")
        city_events.extend(main_events)

        print("\n  Parsing schedule on main...")
        schedule_events = parse_rubric_schedule(city_name, city_path)
        city_events.extend(schedule_events)

        for rubric in rubrics:
            print(f"\n  Parsing rubric: {rubric['name']}...")

            if city_name == 'Минск':
                rubric_url = rubric['path']
            else:
                city_short = city_path.split('/')[2] if city_path != '/' else ''
                rubric_url = f"{rubric['path']}{city_short}/"

            rubric_events = parse_rubric_schedule(city_name, rubric_url)
            city_events.extend(rubric_events)

        unique_events = []
        for event in city_events:
            event_id = event.get('id')
            event_url = event.get('ссылка')

            is_duplicate = False
            if event_id and event_id in seen_ids:
                is_duplicate = True
            elif event_url and event_url in seen_urls:
                is_duplicate = True

            if not is_duplicate:
                if event_id:
                    seen_ids.add(event_id)
                if event_url:
                    seen_urls.add(event_url)
                unique_events.append(event)

        print(f"\n  Unique events: {len(unique_events)}")

        for idx, event in enumerate(unique_events, 1):
            event_url = event.get('ссылка')
            if not event_url:
                all_events.append(event)
                continue

            print(f"    [{idx}/{len(unique_events)}] Detail parsing: {event.get('название', '')[:40]}...")
            detail_data = parse_event_detail(event_url)

            merged = {**event, **detail_data}

            # Если категория не определилась, определяем по названию
            if not merged.get('раздел') and merged.get('название'):
                merged['раздел'] = detect_category(merged['название'])

            required_fields = ['id', 'название', 'раздел', 'город', 'место',
                             'дата_начала', 'дата_конца', 'цена_мин', 'цена_макс',
                             'возраст', 'описание', 'постер', 'ссылка']

            for field in required_fields:
                if field not in merged or merged[field] is None:
                    merged[field] = None

            all_events.append(merged)

        print(f"\n  Total for {city_name}: {len(unique_events)}")

    return all_events


def save_to_csv(events: List[Dict[str, any]], filename: str = 'afisha_events.csv'):
    if not events:
        print("No data to save")
        return

    import csv

    headers = ['id', 'название', 'раздел', 'город', 'место',
               'дата_начала', 'дата_конца', 'цена_мин', 'цена_макс',
               'возраст', 'описание', 'постер', 'ссылка']

    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()

        for event in events:
            clean_event = {}
            for key, value in event.items():
                if key not in headers:
                    continue
                if isinstance(value, str):
                    clean_event[key] = ' '.join(value.split())
                elif isinstance(value, (int, float)):
                    clean_event[key] = value
                else:
                    clean_event[key] = str(value) if value else None
            writer.writerow(clean_event)

    print(f"Data saved to {filename}")


def run_parser():
    cities = {
        'Минск': '/',
        'Гомель': '/all/gomel/',
        'Гродно': '/all/grodno/',
        'Витебск': '/all/vitebsk/',
        'Брест': '/all/brest/',
        'Могилев': '/all/mogilev/'
    }

    print("="*60)
    print("Starting parser for Relax.by")
    print(f"Cities: {', '.join(cities.keys())}")
    print("="*60)

    all_events = parse_all_cities(cities)

    json_file = 'afisha_events.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    save_to_csv(all_events)

    print(f"\n{'='*60}")
    print(f"TOTAL events collected: {len(all_events)}")
    print(f"JSON: {json_file}")
    print(f"CSV: afisha_events.csv")
    print(f"{'='*60}")

    if all_events:
        print("\nStatistics:")
        events_with_dates = [e for e in all_events if e.get('дата_начала')]
        events_with_prices = [e for e in all_events if e.get('цена_мин')]
        events_with_place = [e for e in all_events if e.get('место')]

        print(f"  With dates: {len(events_with_dates)}")
        print(f"  With prices: {len(events_with_prices)}")
        print(f"  With place: {len(events_with_place)}")

        print("\nExamples of collected events:")
        for i, event in enumerate(all_events[:5], 1):
            if event.get('название'):
                print(f"\n{i}. {event.get('название')}")
                print(f"   City: {event.get('город')}")
                print(f"   Link: {event.get('ссылка')}")
                if event.get('дата_начала'):
                    print(f"   Date: {event.get('дата_начала')} - {event.get('дата_конца') or event.get('дата_начала')}")
                if event.get('цена_мин'):
                    print(f"   Price: {event.get('цена_мин')} - {event.get('цена_макс')} rub.")
                if event.get('место'):
                    print(f"   Venue: {event.get('место')}")
                if event.get('возраст'):
                    print(f"   Age: {event.get('возраст')}")

    print("\n" + "="*60)
    print("Saving events to database...")
    print("="*60)
    asyncio.run(save_events_to_db(all_events))


if __name__ == "__main__":
    run_parser()