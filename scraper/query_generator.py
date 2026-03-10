"""
Dynamic query generator for worldwide Google Maps scraping.
Generates search queries from all configured cities × categories,
and tracks which queries have already been scraped to avoid duplicates.
"""
import logging
from database.db import get_connection

logger = logging.getLogger(__name__)

# Comprehensive list of Indian cities by state/region
INDIA_CITIES = {
    # North India
    "Delhi": ["Connaught Place Delhi", "Karol Bagh Delhi", "Lajpat Nagar Delhi",
              "Rajouri Garden Delhi", "Saket Delhi", "Dwarka Delhi",
              "Rohini Delhi", "Pitampura Delhi"],
    "NCR": ["Noida", "Greater Noida", "Gurgaon", "Faridabad", "Ghaziabad"],
    "Punjab": ["Chandigarh", "Ludhiana", "Amritsar", "Jalandhar", "Patiala",
               "Mohali", "Bathinda", "Pathankot"],
    "Haryana": ["Karnal", "Panipat", "Ambala", "Hisar", "Rohtak"],
    "Uttar Pradesh": ["Lucknow", "Agra", "Varanasi", "Kanpur", "Prayagraj",
                      "Meerut", "Bareilly", "Aligarh", "Gorakhpur"],
    "Rajasthan": ["Jaipur", "Udaipur", "Jodhpur", "Kota", "Ajmer", "Bikaner"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Rishikesh", "Mussoorie"],
    "Jammu & Kashmir": ["Srinagar", "Jammu"],
    "Himachal Pradesh": ["Shimla", "Manali", "Dharamshala"],

    # West India
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad",
                    "Thane", "Navi Mumbai", "Andheri Mumbai", "Bandra Mumbai",
                    "Powai Mumbai", "Juhu Mumbai"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"],
    "Goa": ["Goa", "Panaji", "Margao"],

    # South India
    "Karnataka": ["Bangalore", "Mysore", "Mangalore", "Hubli",
                  "Koramangala Bangalore", "Indiranagar Bangalore",
                  "Whitefield Bangalore", "Jayanagar Bangalore",
                  "HSR Layout Bangalore", "Electronic City Bangalore"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Trichy", "Salem",
                   "Anna Nagar Chennai", "T Nagar Chennai", "Adyar Chennai"],
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur"],
    "Telangana": ["Hyderabad", "Secunderabad", "Warangal",
                  "Jubilee Hills Hyderabad", "Banjara Hills Hyderabad",
                  "Hitech City Hyderabad", "Gachibowli Hyderabad"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Tirupati", "Guntur"],

    # East India
    "West Bengal": ["Kolkata", "Howrah", "Salt Lake Kolkata", "Park Street Kolkata"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Puri"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad"],
    "Assam": ["Guwahati", "Dibrugarh"],

    # Central India
    "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior"],
    "Chhattisgarh": ["Raipur", "Bilaspur"],
}

# International cities by country
INTERNATIONAL_CITIES = {
    "USA": [
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
        "San Antonio", "San Diego", "Dallas", "Austin", "San Jose",
        "Miami", "Atlanta", "Denver", "Seattle", "Boston",
        "Las Vegas", "Portland", "Nashville", "Orlando", "Tampa",
        "Charlotte", "Minneapolis", "Raleigh", "Salt Lake City",
        "San Francisco", "Brooklyn New York", "Manhattan New York",
        "Scottsdale Arizona", "Plano Texas", "Irvine California",
    ],
    "UK": [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow",
        "Liverpool", "Edinburgh", "Bristol", "Sheffield", "Nottingham",
        "Leicester", "Cardiff", "Brighton", "Oxford", "Cambridge",
        "Reading", "Southampton", "Newcastle", "Belfast", "York",
    ],
    "Canada": [
        "Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa",
        "Edmonton", "Winnipeg", "Quebec City", "Hamilton", "Halifax",
        "Victoria", "Mississauga", "Brampton", "Surrey",
    ],
    "Australia": [
        "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
        "Gold Coast", "Canberra", "Hobart", "Darwin", "Cairns",
        "Newcastle Australia", "Wollongong",
    ],
    "UAE": [
        "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah",
        "Fujairah", "Al Ain",
    ],
    "Singapore": ["Singapore"],
    "New Zealand": ["Auckland", "Wellington", "Christchurch", "Hamilton New Zealand"],
    "Ireland": ["Dublin", "Cork", "Galway", "Limerick"],
    "South Africa": ["Johannesburg", "Cape Town", "Durban", "Pretoria"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne",
                "Stuttgart", "Dusseldorf"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
    "France": ["Paris", "Lyon", "Marseille", "Nice", "Toulouse", "Bordeaux"],
    "Italy": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Malaga"],
    "Saudi Arabia": ["Riyadh", "Jeddah", "Mecca", "Medina", "Dammam"],
    "Qatar": ["Doha"],
    "Bahrain": ["Manama"],
    "Kuwait": ["Kuwait City"],
    "Oman": ["Muscat"],
    "Malaysia": ["Kuala Lumpur", "Penang", "Johor Bahru"],
    "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya"],
    "Philippines": ["Manila", "Cebu", "Davao"],
    "Indonesia": ["Jakarta", "Bali", "Surabaya", "Bandung"],
    "Japan": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya"],
    "South Korea": ["Seoul", "Busan", "Incheon", "Daegu"],
    "Hong Kong": ["Hong Kong"],
    "Taiwan": ["Taipei", "Kaohsiung"],
    "Vietnam": ["Ho Chi Minh City", "Hanoi", "Da Nang"],
    "Mexico": ["Mexico City", "Cancun", "Guadalajara", "Monterrey"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Belo Horizonte"],
    "Colombia": ["Bogota", "Medellin", "Cartagena"],
    "Argentina": ["Buenos Aires", "Cordoba", "Rosario"],
    "Chile": ["Santiago", "Valparaiso"],
    "Nigeria": ["Lagos", "Abuja", "Port Harcourt"],
    "Kenya": ["Nairobi", "Mombasa"],
    "Egypt": ["Cairo", "Alexandria"],
    "Turkey": ["Istanbul", "Ankara", "Izmir", "Antalya"],
    "Pakistan": ["Karachi", "Lahore", "Islamabad", "Rawalpindi"],
    "Bangladesh": ["Dhaka", "Chittagong"],
    "Sri Lanka": ["Colombo", "Kandy"],
    "Nepal": ["Kathmandu", "Pokhara"],
}

# Business categories to target
DEFAULT_CATEGORIES = [
    "restaurants",
    "clinics",
    "dentists",
    "gyms",
    "pet shops",
    "car wash",
    "laundry",
    "salons",
    "spas",
    "cafes",
    "bakeries",
    "pharmacies",
    "veterinary clinics",
    "physiotherapy",
    "yoga studios",
    "coaching centers",
    "tuition centers",
]


def generate_all_queries(categories=None, include_international=True):
    """
    Generate all possible (query, city, country) tuples.
    Returns a list of (query_string, city_name, country).
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    queries = []

    # India queries
    for state, cities in INDIA_CITIES.items():
        for city in cities:
            for category in categories:
                query = f"{category} in {city}"
                queries.append((query, city, "India"))

    # International queries
    if include_international:
        for country, cities in INTERNATIONAL_CITIES.items():
            for city in cities:
                for category in categories:
                    query = f"{category} in {city}"
                    queries.append((query, city, country))

    logger.info(f"Generated {len(queries)} total query combinations")
    return queries


def generate_india_queries(categories=None):
    """Generate queries for India only."""
    return generate_all_queries(categories=categories, include_international=False)


def generate_international_queries(categories=None):
    """Generate queries for international only."""
    if categories is None:
        categories = DEFAULT_CATEGORIES

    queries = []
    for country, cities in INTERNATIONAL_CITIES.items():
        for city in cities:
            for category in categories:
                query = f"{category} in {city}"
                queries.append((query, city, country))

    logger.info(f"Generated {len(queries)} international queries")
    return queries


def get_unscraped_queries(all_queries):
    """
    Filter out queries that have already been scraped (ever).
    Returns only queries that have never been run before.
    """
    conn = get_connection()
    scraped = set()
    try:
        rows = conn.execute("SELECT query FROM scraped_queries").fetchall()
        scraped = {row["query"] for row in rows}
    except Exception:
        pass  # Table might not exist yet
    finally:
        conn.close()

    unscraped = [(q, city, country) for q, city, country in all_queries if q not in scraped]
    logger.info(f"Unscraped queries: {len(unscraped)} out of {len(all_queries)}")
    return unscraped


def mark_query_scraped(query, city, country, results_count):
    """Record a query as scraped in the database."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO scraped_queries
               (query, city, country, results_count)
               VALUES (?, ?, ?, ?)""",
            (query, city, country, results_count),
        )
        conn.commit()
    finally:
        conn.close()


def get_country_for_city(city):
    """Look up which country a city belongs to."""
    for state, cities in INDIA_CITIES.items():
        if city in cities:
            return "India"
    for country, cities in INTERNATIONAL_CITIES.items():
        if city in cities:
            return country
    return None


if __name__ == "__main__":
    queries = generate_all_queries()
    india_count = sum(1 for _, _, c in queries if c == "India")
    intl_count = len(queries) - india_count
    countries = set(c for _, _, c in queries)
    print(f"Total queries: {len(queries)}")
    print(f"  India: {india_count}")
    print(f"  International: {intl_count}")
    print(f"  Countries: {len(countries)}")
    print(f"\nSample queries:")
    for q, city, country in queries[:10]:
        print(f"  [{country}] {q}")
