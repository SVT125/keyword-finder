# keyword-finder
Finds the k best keywords on a given webpage. Usage example:
```
python main.py https://signalscv.com/2017/05/28/man-receives-ticket-hitting-88-mph-delorean/
```
## Requirements

* [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy)
  * [python-Levenshtein](https://github.com/ztane/python-Levenshtein/), optional for faster computation
* [requests](http://docs.python-requests.org/en/master/)
* [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
* [NLTK](http://www.nltk.org/)



## Description

This was a weekend, 48 hour project I did for an interview - the prompt was to, given a webpage URL, find the best keywords that describe the page. For example, this [example article](https://signalscv.com/2017/05/28/man-receives-ticket-hitting-88-mph-delorean/) might have the keywords "88", "DeLorean", "'Back To The Future'", "car", etc. 

My take on this is multi-segmented, and employs various filters along the way. The process is as follows:
1. Filter out all characters in each token that are not alphanumeric or the dash character (-). This is so as to filter out any noise that might be in some tokens e.g. “softly…”, “ending; when”, etc. This also defines a parseable token as one with only alphanumeric characters + the dash character, and I include the dash character and numbers strictly for product names. If no product/brand names should be considered, then I would restrict the set of valid characters to only the alphabet.
2. Omit all tokens of length < T, in the code T = 4. This is moreso a precaution against considering tokens which are common English words/qualifiers, like “the”, “and”, etc. The lowest T should possibly be is 3, since I don’t think there are many pages for which a valid token is of length <= 2. On the other hand, I set T = 4 in the code as a quick shortcut to remove those aforementioned English words, at the slight cost of losing 3-letter tokens like “pie” or “art”.
3. If a token is all uppercase, turn to all lowercase. In the event the webpage has special text seen in all caps e.g. a disclaimer or ruleset, I add this rule as I believe more likely than not a fully uppercased token bears no difference in meaning if turned to fully lowercased.
4. All tokens start and end with any number of optional numbers, but can only contain alphabetic letters in the middle. I assume here that there aren’t many significant tokens which have a number in the middle of them, but still consider prefix/suffixed numbers in the tokens e.g. “4chan”, “CPT-122”.
5. Filter out all common words. This is somewhat intertwined with step b). Simply put, the ideal set of common words to filter out would be the set of non-nouns seen in the n-most common words in the English language e.g. n = 10K in my chosen dataset. With this, a good portion of “false-positive” topics are omitted. In the code, I simply take a small subset of words I thought should be omitted out of the first 150 words in the above link – as I note in the comments, if a full exhaustive dictionary of words is required, then perhaps a giant Python list of words in a separate file would be best, or reading from an external text file if initialization rarely occurs.
6. Filter out all non-nouns. Also mentioned above, I implement this via the NLTK lib, a popular natural language processing library. In particular, NLTK has the ability to assign categorizations for each token e.g. adverb, noun, etc. So, I simply filtered only for tokens which were deemed as nouns of any kind e.g. proper noun, plural noun, etc. as is defined in this tagset. Given that the library is open source and trained on massive amounts of data, I expect a very minimal amount of false classifications.

At this point, I have a list exclusively of the tokens I would consider valid topics (for the most part – the words that probably shouldn’t be tokens should by this point have a small count versus what would be the actual topics). I then count the number of occurrences per token on the page with a hash table in trivial linear time and space. To find the k most common tokens seen on the page, I use a k-size min heap which as an invariant will store the k most common tokens from the token keys that have been sent through it so far – this is done by, for each token key in the hash table, compare its count to the top of the min heap/minimum count token of the k best tokens so far. If it is greater than the top of the min heap, pop the top and add the current token in, otherwise do nothing. Overall, this takes O(n + m log k) time and O(m+k) space, where n = the number of tokens, m = the number of unique tokens, and k = k. 

I also note that heapq.nlargest(…) essentially solves this step, but I wasn’t sure of its time and space complexity and chose to code out the solution instead, thinking it’d be faster as it’s familiar in memory.

On the side, I do a little extra reducing by first keeping track of the tokens which have at least 1 uppercased character. After creating the token count dictionary, I check to see if these special tokens when lowercased are also seen in the dictionary – if so, then add the lowercased counts to the uppercased counts and delete the lowercased version from the dictionary. I came up with this rule in lieu of tokens like “toaster” vs. “Toaster,” for which I decided the uppercased version was the better one to keep since the uppercased version might be a product/brand name, and there’s no problem in having “Toaster” vs. “toaster” as a selected topic word. This takes an additional O(n) time and space, which does not affect the overall performance of this whole reduction step.

The second post-reduction involved concerns the meta tags of a webpage. As with the actual body text tokens, I tokenize the contents of the title and description meta tags, filter them, then use them to apply a greater weight to their existing entries in the count dictionary if they have entries, in the form of multiplying their final entry count by a scalar factor. Certainly, the approach of giving greater weight to tokens also seen in the meta tags can vary, but multiplying by a scalar factor of 1.5 was the quick and obvious solution I saw, and it seemed to sift out a small handful of topics that might otherwise show in the final results.

The third and final post-reduction I was able to implement utilizes fuzzy string matching. Basically, I saw that some webpages in their final results had tokens like “Toaster” and “toast,” so I thought to use the fuzzywuzzy python lib w/ python-Levenshtein to compare all the final tokens together (naively in quadratic time) and combine their entries if their fuzzy match score exceeded a set threshold, in the code set to 90. Specifically, the entry that is deleted is the shorter of the two in length, while the longer entry in the pair appends the former’s count – I added this distinction since for a corner set of tokens this might make a difference e.g. “read” over “reader.” If only prefix/suffix/substring matching is required, then the purpose of this step might be achieved in faster time. 

In summary, I apply the following ideas:

1. Filter out all non-alphanumeric characters + non-dash characters
2. Omit short length tokens
3. Lowercase all tokens
4. All tokens can only have numerics at their ends
5. Omit all tokens that are considered common in English
6. All tokens must be nouns
7. Merge tokens originally w/ a leading uppercase
8. Add bias towards tokens seen in the metatags
9. Merge similar tokens

Certainly the existing ideas can be improved and more ideas can be added to fine tune the results returned, but this is what I thought of within that 48-hour time span. It was certainly a great "mini-hackathon" project!
