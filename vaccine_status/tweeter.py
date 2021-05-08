"""
Scraps https://covid19asi.saglik.gov.tr/ for vaccination results
and tweets results
"""
import os

import logging
import re

import requests
from bs4 import BeautifulSoup

import twitter

class VacScraper:
    """
    Scrapes https://covid19asi.saglik.gov.tr/
    """
    # Source: https://data.tuik.gov.tr/Bulten/Index?p=Adrese-Dayali-Nufus-Kayit-Sistemi-Sonuclari-2020-37210
    TURKEY_POPULATION = 83_614_362  # As of 12/31/2020

    STATUS_URL = 'https://covid19asi.saglik.gov.tr/'
    SVG_SELECTOR = '.svg-turkiye-haritasi'

    SECOND_DOSE_REGEX = r'var asiyapilankisisayisi2Doz \= (\d+)'
    LAST_UPDATED_REGEX = r"var asisayisiguncellemesaati \= \'(.+)\'"
    DATE_FORMAT = ''

    def __init__(self):
        self.logger = logging.getLogger('vacscraper')
        self.soup = self.fetch()

    def fetch(self) -> BeautifulSoup:
        """
        Retrieves `STATUS_URL` and create a soup
        """
        response = requests.get(VacScraper.STATUS_URL)
        self.logger.info(f"Fetched Vaccine status with code {response.status_code}")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup

    def get_vaccine_status(self) -> (float, str):
        """
        Status percantage is calcualted by:
            second_dose_numbers / TURKEY_POPULATION
        Retrieves second dose numbers from scraped website.
        Pre-JS, the values are stored in a <script> tag under `SVG_SELECTOR` dom element.
        like: <script>var asiyapilankisisayisi2Doz = 9730410;</script>
        Can retrieve the number with simple regex
        Returns:
            (Ratio of second dose per population,
             Last updated timestamp)
        """
        svg_el = self.soup.select_one(VacScraper.SVG_SELECTOR)
        script_els = svg_el.find_all('script')
        # Likely the order of script tags never change
        # But gonna loop jusut in case
        # Last updated comes as a localized string, no need to alter it so I'll keep it as is
        last_updated = None
        second_dose = None
        self.logger.debug(f"Script tags:\n\t{script_els}")
        for script_el in script_els:
            if match := re.match(VacScraper.LAST_UPDATED_REGEX, script_el.string):
                last_updated = match[1]
            elif match := re.match(VacScraper.SECOND_DOSE_REGEX, script_el.string):
                second_dose = match[1]
        assert last_updated, "Missing last updated."
        assert second_dose, "Missing second dose."
        second_dose_ratio = round(int(second_dose) / VacScraper.TURKEY_POPULATION, 4)
        self.logger.info(f"Ratio: {second_dose_ratio} Last Updated: {last_updated}")
        return second_dose_ratio, last_updated

class Tweeter:
    """
    Posts tweets
    """

    FULL_PROGRESS_CHAR = '▓'
    EMPTY_PROGRESS_CHAR = '░'
    LENGTH_PROGRESS = 20

    def __init__(self, consumer_key: str, consumer_secret: str,
                 access_token_key: str, access_token_secret: str):
        """
        Initializes a tweeter.
        Expects a user token, retrieve a user token using twitter 3legged oauth
        """
        self.logger = logging.getLogger('Tweeter')
        self.twitter_api = twitter.Api(consumer_key=consumer_key,
                                       consumer_secret=consumer_secret,
                                       access_token_key=access_token_key,
                                       access_token_secret=access_token_secret)
        
  
    def post_tweet(self, tweet: str, **kwargs):
        """
        Posts a preformatted tweet
        In minimum it requires a tweet
        kwargs are passed to api directly. Detailed documentation:
        https://python-twitter.readthedocs.io/en/latest/twitter.html#twitter.api.Api.PostUpdate
        """
        self.logger.info(f'Tweeting:\n\t{tweet}\n\tkwargs: {kwargs}')
        status = self.twitter_api.PostUpdate(tweet, **kwargs)
        self.logger.debug(f"{status.id} / {status.text}")

    def create_percentage_tweet(self, ratio: float) -> str:
        """
        Converts a ratio to percentage tweet.
        Locality will be in Turkish
        """
        full_amount = int(ratio * Tweeter.LENGTH_PROGRESS // 1)  # In smallest integer.
        # To localize, I'll just replace . with , It is the simplest solution.
        # No need to mess with localization settings.
        percentage_value = f"{ratio * 100.0:.4n}".replace('.', ',')
        percentage_tweet = f'{Tweeter.FULL_PROGRESS_CHAR * full_amount:{Tweeter.EMPTY_PROGRESS_CHAR}<20} %{percentage_value}'
        self.logger.debug(f'Created percentage tweet with {ratio}\n{percentage_tweet}')
        return percentage_tweet

def main():
    """
    The entry function.
    Pulls data from the website and tweets it.
    """
    logger = logging.getLogger('main')
    # Get credentials from env variables.
    consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
    consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')
    access_key = os.getenv('TWITTER_ACCESS_KEY')
    secret_key = os.getenv('TWITTER_SECRET_KEY')
    logger.debug(f'{consumer_key}, {consumer_secret}, {access_key}, {secret_key}')
    tweeter = Tweeter(consumer_key, consumer_secret, access_key, secret_key)
    try:
        scraper = VacScraper()
        ratio, last_updated = scraper.get_vaccine_status()
    except (requests.HTTPError, AssertionError):
        logger.exception(f"Scraping failed.")
        raise
    try:
        perc_tweet = tweeter.create_percentage_tweet(ratio)
        tweeter.post_tweet(perc_tweet)
    except:
        logger.exception(f"Tweeting failed.")
