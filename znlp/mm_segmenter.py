#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright Zeta Co., Ltd.
## written by @moeseth based on research by @aye_hnin_khine

from matched_word import MatchedWord
import mm_syllablebreak
import mm_normalizer
import mm_tokenizer
import mm_converter
import mm_detector
import codecs
import json
import re
import os

class Segmenter():
    def __init__(self, sql_manager=None, burmese_df_path=None):
        if sql_manager:
            self.sql_manager = sql_manager
        else:
            self.sql_manager = None

        if burmese_df_path:
            self.burmese_df_path = burmese_df_path
        else:
            curr_path = os.path.dirname(os.path.abspath(__file__))
            WORDS_FILE = os.path.join(curr_path, "burmese_df.txt")
            self.burmese_df_path = WORDS_FILE

        self.total_counted_documents = 0
        self.words_array = []
        self.words_dict = {}
        self.segmented_matches = []
        self.__load_dictionary()


    def __load_dictionary(self):
        if self.sql_manager is None:
            with codecs.open(self.burmese_df_path, "rb", "utf-8") as f:
                lines = f.readlines()

                ## we will assume our total documents count is the biggest df in the words_df.txt file
                biggest_tdc = 0

                for line in lines:
                    line = line.strip()

                    if len(line) > 0 and not line.startswith("#"):
                        word, df = line.split(",")
                        df =  int(df)

                        self.words_dict[word] = df
                        self.words_array.append(word)

                        if int(df) > biggest_tdc:
                            biggest_tdc = int(df)

                self.total_counted_documents = biggest_tdc

        else:
            ## change query
            query = """ select word from burmese_dictionary
                        where is_deleted = 0 and syllable_count > 1
                        order by syllable_count DESC, length DESC
                    """
            results = self.sql_manager.execute(query, [])

            for r in results:
                word = r["word"]
                word = word.strip()

                self.words_array.append(word)


    def sanitize_string(self, input_string=None):
        if type(input_string) is not unicode:
            input_string = unicode(input_string, "utf8")

        if mm_detector.is_zawgyi(input_string=input_string):
            input_string = mm_converter.zawgyi_to_unicode(input_string=input_string)

        input_string = mm_normalizer.normalize(input_string=input_string)

        ## remove spaces between myanmar words
        ## use positive lookahead to matches \s that is followed by a [\u1000-\u104F], without making the [\u1000-\u104F] part of the match
        input_string = re.sub(u"([\u1000-\u104F])\s+(?=[\u1000-\u104F])", r"\1", input_string)

        return input_string


    def put_back_segmented_matches(self, token):
        token_length = len(token)
        word_length = 0
        ordered_words = []

        ## since we replaced with same length,
        ## this function needs to be able to find back the same string with same length
        while word_length != token_length:
            word_obj = self.segmented_matches.pop(0)
            word = word_obj.word
            word_length += len(word)

            ordered_words.append(word)

        return ordered_words


    def segment(self, input_string):
        input_string = self.sanitize_string(input_string=input_string)
        segmented_words = []
        self.segmented_matches = []

        if len(input_string) > 0:
            for key in self.words_array:
                if key in input_string:
                    matches = re.finditer(key, input_string)

                    for match in matches:
                        length = len(key)
                        ## if string behind is all good
                        match_start_position = match.start()

                        ## also need to check previous string for VIRAMA Killer
                        previous_string = input_string[match_start_position-1:]
                        if re.search(u"^\u1039", previous_string):
                            continue

                        temp_string = input_string[match_start_position:]
                        is_valid_syllablebreak = mm_syllablebreak.is_valid_syllablebreak(temp_string, length)

                        if is_valid_syllablebreak:
                            to_replace = u"\uFFF0" * length
                            ## replacing string at index
                            input_string = input_string[:match_start_position] + to_replace + input_string[match_start_position + length:]

                            matched_word = MatchedWord(key, match.start())
                            self.segmented_matches.append(matched_word)

                            ## sort matches by start position
                            self.segmented_matches = sorted(self.segmented_matches, key=lambda x: x.start)


            tokens = mm_tokenizer.get_tokens(input_string=input_string)

            for token in tokens:
                if u"\uFFF0" in token:
                    ## if non \u00D2 in the string
                    ## split non \u00D2 and \u00D2
                    if re.search(u"[^\uFFF0]", token):
                        ## add space between non \ufff0 and \ufff0
                        token = re.sub(u"([^\uFFF0])(\uFFF0)", u"\1 \2", token)
                        token = re.sub(u"(\uFFF0)([^\uFFF0])", u"\1 \2", token)

                        inside_tokens = mm_tokenizer.get_tokens(input_string=token)

                        for inside_token in inside_tokens:
                            if u"\uFFF0" in inside_token:
                                ordered_words = self.put_back_segmented_matches(inside_token)
                                segmented_words.extend(ordered_words)
                            else:
                                segmented_words.append(inside_token)
                    else:
                        ordered_words = self.put_back_segmented_matches(token)
                        segmented_words.extend(ordered_words)

                elif len(token) > 0:
                    segmented_words.append(token)


        return segmented_words


'''
aa = Segmenter()
#s = u"ဖြစ်ပါတယ်။ ဆောက်လုပ်ရေးဝန်ကြီးဌာန၊ လမ်းဦးစီး ဌာနက တာဝန်ယူထားတဲ့လမ်းလည်းဖြစ်ပါတယ်။ မိုင် ၂၀ ရှည်ပါတယ်။ န.၀.တ၊ န.အ.ဖ အစိုးရ လက်ထက်က မြို့လူထုရဲ့ လုပ်အားနဲ့ ဖောက်လုပ်ခဲ့တဲ့လမ်းဖြစ်ပါတယ်။ ၂၀၀၃ ခုနှစ်ကစပြီးတော့ ကတ္တရာလမ်းခင်းနေတာ ယခု ၂၀၁၇ ခုနှစ်အထိ ဆိုရင် ၁၄ နှစ်မှာ ၁၀ မိုင်သာသာပဲရှိနေပါသေး တယ်။ ကျန် ၁၀ မိုင်ကတော့ ကျောက်ကြမ်းလမ်းအဆင့်ပဲရှိနေပါတယ်။ ယခုမြင်ရတဲ့ပုံကတော့ အခု တင်ပြမယ့် မဟာဗျူဟာလမ်းမကြီးနှင့် ချိတ်ဆက်ထားတဲ့ ဗောဓိပင်-ချောင်းဆုံ-တော်ကလပ်လမ်းပဲဖြစ်ပါတယ်။ ၎င်းလမ်းကို ကျေးရွာအုပ်စုငါးအုပ်စုဖြစ်တဲ့ ဗောဓိပင်ကျေးရွာအုပ်စု၊ တော်ကလပ်ကျေးရွာအုပ်စု၊ ရှမ်းစုကျေးရွာအုပ်စု၊ ရေလျှံကျေးရွာအုပ်စုနှင့် ယွန်းသွယ်ကျေးရွာအုပ်စုများက အိမ်ထောင်စုပေါင်း ၄၂၃၈ စု၊ လူဦးရေပေါင်း ၁၆၆၀၇ ဦးတို့ နေ့စဉ် အသုံးပြု နေတဲ့မြေသားလမ်းပဲ ဖြစ်ပါတယ်။ ကျေးလက်လမ်းတံတားမဟာဗျူဟာအရဆိုလို့ရှိရင် ၎င်းလမ်းများကို ၃၆ တန်ခံကတ္တရာလမ်း သို့မဟုတ် ကွန်ကရစ်လမ်း၊ ကွန်ကရစ်တံတားများအဖြစ် ဆောင်ရွက်ပေးရမှာဖြစ်ပါတယ်။ လက်ရှိ လက်ပံတန်း-ကျုံ လဟာ မဟာဗျူဟာလမ်းမကြီးတောင်မှပဲ ကတ္တရာလမ်းအဖြစ် အပြည့်မရသေးတော့ တိုင်းပြည်ကိုလည်းအားနာပါတယ်။ ယခု တင်ပေးတဲ့လမ်း ကို အင်းမကထွက်တဲ့ ဂျင်းကျောက်လို့ခေါ်တဲ့ ဂဝံကျောက်စလစ်ရောမြေအဖြစ် စံချိန်စံညွှန်းမီမီ ဂဝံလမ်းအဆင့်မြှင့်တင်ပေးနိုင်မယ်ဆိုရင်တောင် ကျွန်တော်နဲ့ ကျွန်တော့်မဲဆန္ဒရှင်ပြည်သူတွေ အင်မတန်ဝမ်းသာရမှာဖြစ်ပါတယ်။ သို့ဖြစ်ပါ၍ ဥက္ကဋ္ဌကြီးမှတစ်ဆင့် မေးမြန်းလိုတာကတော့ အရှည် ၂ မိုင် ၇ ဖာလုံ၊ အကျယ် ၁၈ ပေရှိတဲ့ ဗောဓိပင်-ချောင်းဆုံ-တော်ကလပ် မြေသားလမ်းကို အင်းမ ဂျင်းကျောက်ဖြင့် ရာသီမရွေးသွားလာနိုင်တဲ့ဂဝံလမ်းအဆင့်ကို တိုးမြှင့်ပေးနိုင်ခြင်းရှိ/မရှိကို ဥက္ကဋ္ဌကြီး မှတစ်ဆင့် မေးမြန်းအပ်ပါတယ်။ အားလုံး ကျေးဇူးတင်ပါတယ်ခင်ဗျား။"
s = u"ရိုသေလေးစားအပ်ပါတဲ့ပြည်သူ့လွှတ်တော်ဥက္ကဌကြီးနှင့်အားလုံးမင်္ဂလာပါခင်ဗျား။\n\nဥက္ကဌကြီးခင်ဗျား။\n ယခု ကျွန်တော် မေးမယ့်မေးခွန်းကတော့ ကျေးလက်ဦးစီးဌာနက စီမံဆောင်ရွက်ပိုင်ခွင့်ရှိတဲ့မြေသားလမ်းကို ရာသီမရွေးသွားလို့လာလို့ရတဲ့ ဂဝံလမ်းအဖြစ် အဆင့်မြှင့်တင်ပေးနိုင်ခြင်းရှိ/မရှိမေးခွန်းကို မေးမြန်းမှာ ဖြစ်ပါတယ်။\n\nဥက္ကဌကြီး ခင်ဗျား။\n \nကျွန်တော့်မဲဆန္ဒနယ်မြေ လက်ပံတန်းမြို့မှာ ကျေးရွာပေါင်း ၃၃၀ နှင့် လက်ပံတန်းမြို့ကို ချိတ်ဆက်အသုံးပြု နေတဲ့လမ်းမကြီးငါးခုရှိပါတယ်။\n အဲဒီလမ်းတွေကတော့ (၁)ရန်ကုန်-ပြည်လမ်း၊ (၂) ကဗျို ကြီး-ကျွန်းကလေး-လက်ပံတန်းလမ်း ဒီလမ်းက ဆောက်လုပ်ရေးဝန်ကြီးဌာနကတာဝန်ယူ ထားတဲ့လမ်းဖြစ်ပြီးတော့ အရှည် ၆ မိုင်ရှိပြီး ကတ္တရာလမ်းအဆင့်ဖြစ်ပါတယ်။\n\n (၃)လက်ပံတန်းကျုံလဟာ မဟာဗျူဟာလမ်း ၎င်းလမ်းကလည်း ဆောက်လုပ်ရေးဝန်ကြီးဌာနက တာဝန်ယူထားတဲ့ လမ်းဖြစ်ပြီးတော့ အရှည် ၂၀ မိုင်ရှိပါတယ်။\n\n (၄)လက်ပံတန်း-တောင်ချို ကုန်း-သလာဘို-မင်းလှလမ်း ဖြစ်ပါတယ်။\n\n ၎င်းလမ်းက မင်းလှမြို့နယ် နယ်နိမိတ်အထိကို ၇ မိုင်ခန့်ရှိပါတယ်။\n \nအင်္ဂလိပ်အစိုးရ အုပ်ချုပ်စဉ်ကတော့ ကတ္တရာလမ်း၊ ယခုတော့ မြေသားလမ်းဖြစ်ပါတယ်။\n\nဆောက်လုပ်ရေးဝန်ကြီးဌာန ကိုတာဝန်ယူပေးဖို့လည်း တင်ပြထားပြီးဖြစ်ပါတယ်။\n\n(၅) လက်ပံတန်း-သာရဝေါမီးရထားလမ်း ဖြစ်ပါတယ်။\n ဥက္ကဋ္ဌကြီးခင်ဗျား။\n ကျွန်တော် အထက်က တင်ပြထားတဲ့လမ်းမကြီးငါးလမ်းနဲ့ ကျေးရွာအုပ်စု များချိတ်ဆက်ပြီး ဖောက်လုပ်ထားတဲ့ကျေးလက်ဦးစီးဌာနပိုင်လမ်းများကလည်း ကျွန်တော့်မြို့နယ်မှာ အလွန်များပြားလှပါတယ်။\n ကျောက်ချောလမ်းတစ်လမ်းကလွဲရင် ကျန်လမ်းများက အဆင့်မမီတဲ့ မြေနီလမ်းများနှင့် အခြားမြေသားလမ်းများက များပါတယ်။\n အဲဒီလမ်းများဟာ လူဦးရေထောင်ကျော် အသုံးပြု နေတဲ့လမ်းများဖြစ်ပါတယ်။\n ရာသီမရွေးသွားလို့မရတဲ့လမ်းများလည်းဖြစ်ပါတယ်။\n ဥက္ကဋ္ဌကြီး ခင်ဗျား။\nယခု ကျွန်တော် တင်ပြမယ့်လမ်းကတော့ လက်ပံတန်း-ကျုံလဟာ မဟာဗျူဟာလမ်းမကြီးနှင့် ချိတ်ဆက်ထားတဲ့ ဗောဓိပင်-ချောင်းဆုံ-တော်ကလပ်လမ်းပဲဖြစ်ပါတယ်။\n Power Point အသုံးပြုခွင့် ပေးစေလိုပါတယ်။\n ယခု မြင်နေရတဲ့ပုံကတော့ လက်ပံတန်းမြို့ရဲ့အနောက်ဘက်ခြမ်း မြစ်မခမြစ်နှင့် ဧရာဝတီမြစ်ကမ်းဘေးက ရွာတွေနဲ့ လက်ပံတန်းမြို့ကိုသွားလာရာမှာ နေ့စဉ်အသုံးပြု နေတဲ့ လက်ပံတန်း-ကျုံလဟာ မဟာဗျူဟာလမ်းမကြီးဖြစ်ပါတယ်။\nဆောက်လုပ်ရေးဝန်ကြီးဌာန၊ လမ်းဦးစီး ဌာနက တာဝန်ယူထားတဲ့လမ်းလည်းဖြစ်ပါတယ်။\n၂၀၀၃ ခုနှစ်ကစပြီးတော့ ကတ္တရာလမ်းခင်းနေတာ ယခု ၂၀၁၇ ခုနှစ်အထိ ဆိုရင် ၁၄ နှစ်မှာ ၁၀ မိုင်သာသာပဲရှိနေပါသေး တယ်။\n"
#s = u"အားလုံး ကျေးဇူးတင်ပါတယ်ခင်ဗျား။"
s = s.replace(" ","")
print(s)
ans = aa.segment(s)
for i in ans:

    print i.encode('utf8')

    '''