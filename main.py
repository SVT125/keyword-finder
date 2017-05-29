from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup
import requests
import nltk

from collections import defaultdict
import heapq
import sys
import re


class TopicExtractor:
    COMMON_WORDS_LIST = ['the', 'this', 'that', 'with', 'from', 'your', 'have', 'more', 'will', 'about', 'other',
                         'they',
                         'what', 'which', 'their', 'there', 'only', 'when', 'here', 'also', 'would', 'were', 'some',
                         'these',
                         'over', 'into', 'should', 'them', 'after', 'before']
    COMMON_WORDS = {x: 1 for x in COMMON_WORDS_LIST}

    def __init__(self, url, keyword_scalar=1.5):
        if keyword_scalar < 1:
            raise ValueError('The keyword scalar factor can\'t be less than 1.')
        # An excerpt of likely len >= 4 words of the 10K most common English words.
        # This may also be read from IO for huge files if the IO cost is worth, or a separate list in another file.
        self.KEYWORD_SCALAR = keyword_scalar
        self.TOKEN_SIMILARITY_THRESHOLD = 90
        r = requests.get(url)
        self.url = url
        self.text = r.text
        self.__retrieve_tokens()
        self.tokens = self.clean_tokens(self.tokens)

    # Given a list of tokens, filters them out according to a set of rules.
    @staticmethod
    def clean_tokens(tokens):
        """
        We follow these rules:
        1. Filter out all characters not in [a-zA-Z0-9\-]. This can also be done w/ a negated regexp.
        2. Remove all tokens len < 4.
        3. If a token is all upper, turn to all lower <=> assume no token has a special meaning in upper vs. lower.
        4. All tokens follow the format [0-9]*[a-zA-Z\-]+[0-9]*.
        5. Filter out common words e.g. "the"; a hash table hit denotes a filtering.
        6. Filter for only nouns.
        # TODO
        1. Test lower() on all words - if there is a collision, then remove the former word e.g. 'Toaster' and 'toaster'.
            -> This is because I assume it's more often just a normal word that starts the sentence vs. a brand name e.g. Costco.
        """
        SPECIAL_CHARACTERS = re.escape('!@#$%^&*()_=+{}[]|\\'";:<>,./?`~")
        alpha_tokens = list(map(lambda x: re.sub('[{}]'.format(SPECIAL_CHARACTERS), '', x), tokens))
        [x.lower() for x in alpha_tokens if x.isupper()]
        filtered_tokens = list(filter(lambda x: len(x) >= 4
                                     and bool(re.match('[a-zA-Z0-9\-]+', x))
                                     and x.lower() not in TopicExtractor.COMMON_WORDS, alpha_tokens))
        return [x[0] for x in nltk.pos_tag(filtered_tokens) if 'NN' in x[1]]

    # Given the webpage as a string, returns the word tokens in the webpage,
    # excluding all HTML/CSS/JS.
    # TODO - Filter out any invisible elements not seen on page load!
    def __retrieve_tokens(self):
        self.soup = BeautifulSoup(self.text, 'html.parser')
        [s.extract() for s in self.soup(['script', 'style'])]
        self.tokens = self.soup.get_text().split()

    # Returns a list, sorted descending on occurence count of the tokens seen on the page.
    # In essence, this returns the k most prevalent topics on the page.
    # Implemented by counting all unique words w/ a hash table and maintaining a k-size min heap
    # as we go along - the heap represents our current k topics from the words seen so far.
    # O(n + m log k), n = len(tokens), m = len(set(tokens)), k = k.
    # Note, there's also heapq.nlargest(...) but I wasn't sure of its time complexity.
    #
    # Additionally, appends token counts for which their versions may differ only by upper/lower casing.
    # TODO - Can finish early if the most seen token so far has count T and we have T-1 tokens left to parse.
    # TODO - For k = 1, linear traversal. For k > n/2, invert the function.
    def __get_k_top_tokens(self, k):
        count_dict = defaultdict(int)
        upper_count_list = []
        heap = []
        for i in range(0, len(self.tokens)):
            token = self.tokens[i]
            if any(x.isupper() for x in token):
                upper_count_list.append(token)
            count_dict[token] += 1

        # If a token when lowercased matches another token, add the lowercased count to this.
        # Assume more often than not the version containing uppercases is the better choice e.g. Amazon vs amazon.
        for token in upper_count_list:
            if token.lower() in count_dict:
                count_dict[token] += count_dict[token.lower()]
                del count_dict[token.lower()]

        # Give greater weights to tokens seen in the relevant meta tags e.g. title, description.
        # The "greater weights" are implemented by multiplying the matching counts by a scalar factor.
        keywords = self.__parse_meta_tags()
        for keyword in keywords:
            if keyword in count_dict:
                count_dict[keyword] *= self.KEYWORD_SCALAR

        # Fuzzy string matching for tokens like "Toaster", "Toast", and "toaster".
        # If there is an approximate match, combine the 2 like tokens.
        # Unfortunately, this takes quadratic/O(n^2) time just to compare every string to every other.
        # Checks all pairs - if fuzzy string comparison is above the constant threshold, note the pair to reduce later.
        count_keys = list(count_dict.keys())
        similars = []
        for i in range(0, len(count_dict)):
            for j in range(i+1, len(count_dict)):
                outer, inner = count_keys[i], count_keys[j]
                if fuzz.ratio(outer, inner) > self.TOKEN_SIMILARITY_THRESHOLD:
                    similar_pair = (outer, inner) \
                        if len(outer) > len(inner) else (inner, outer)
                    similars.append(similar_pair)
        for pair in similars:
            count_dict[pair[0]] += count_dict[pair[1]]
            del count_dict[pair[1]]

        for token in count_dict:
            if len(heap) < k:
                heap.append((count_dict[token], token))
            elif count_dict[token] > heap[0][0]:
                heapq.heappop(heap)
                heapq.heappush(heap, (count_dict[token], token))

        return [heapq.heappop(heap) for i in range(0, k)]

    # TODO - More work can be done to parse more tags e.g. if article, read article meta tags for section, etc.
    # I assume that tokens in the meta tags will have a decent count in the text of the actual webpage.
    def __parse_meta_tags(self):
        is_descriptor = lambda x: x.get('name') == 'description' or \
                                  x.get('property') == 'description' or x.get('itemprop') == 'description'
        keywords = ''.join([meta['content'] for meta in self.soup('meta') if is_descriptor(meta)])
        if self.soup.title.string:
            keywords += ' ' + self.soup.title.string
        return set(self.clean_tokens(keywords.split()))

    def get_topics(self, k=5):
        token_counts = self.__get_k_top_tokens(k)
        k_topics = [x[1] for x in token_counts]
        return k_topics


# TODO - Consider e.g. the toaster link has topics 2-slice toaster, compact toaster) -> greedy matching?
def main():
    if len(sys.argv) < 2:
        print('You must provide exactly 1 URL to parse.')
        return
    for arg in sys.argv[1:]:
        try:
            extractor = TopicExtractor(str(arg))
        except requests.exceptions.MissingSchema as mse:
            print('Invalid URL supplied: {}'.format(str(arg)))
            return
        print('k={}: {}'.format(5, extractor.get_topics(5)))

main()
