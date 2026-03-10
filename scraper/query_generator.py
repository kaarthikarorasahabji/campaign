"""
Dynamic query generator for India-scale Google Maps scraping.
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


def generate_all_queries(categories=None, cities_dict=None):
    """
    Generate all possible (query, city, country) tuples.
    Returns a list of (query_string, city_name, country).
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES
    if cities_dict is None:
        cities_dict = INDIA_CITIES

    queries = []
    for state, cities in cities_dict.items():
        for city in cities:
            for category in categories:
                query = f"{category} in {city}"
                queries.append((query, city, "India"))

    logger.info(f"Generated {len(queries)} total query combinations")
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


if __name__ == "__main__":
    queries = generate_all_queries()
    print(f"Total queries: {len(queries)}")
    for q, city, country in queries[:20]:
        print(f"  {q}")
    print(f"  ... and {len(queries) - 20} more")
