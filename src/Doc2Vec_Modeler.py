import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

import gensim
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.linear_model import LogisticRegression, LinearRegression
from scipy.spatial.distance import cosine, euclidean
from scipy.stats import ttest_ind

from prepare_data import save_in_pkl, read_in_pkl

class Doc2VecModeler(object):
    '''
    Uses Gensim's Doc2Vec model to keep track of different model variations for comparison
    '''
    def __init__(self, model_name, train_corpus, training_corpus_name,
                 vector_size=100, dm=1, min_count=2, epochs=100):
        self.model_name = model_name
        self.train_corpus = train_corpus
        self.n_training_docs = len(self.train_corpus)
        self.training_corpus_name = training_corpus_name
        self.vector_size = vector_size
        self.dm = dm
        self.min_count = min_count
        self.epochs = epochs
        self.inferred_vecs = {'docs': [], 'vecs': []}

    def fit_model(self, verbose=False):
        '''Builds and trains model according to specifications
        CREDIT: Adapted from Gensim's Doc2Vec Tutorial https://github.com/RaRe-Technologies/gensim/blob/develop/docs/notebooks/doc2vec-lee.ipynb
        INPUT: Model specifications (when instantiated), verbose
        OUTPUT: Trained Doc2Vec model
        '''
        model = gensim.models.doc2vec.Doc2Vec(vector_size=self.vector_size,
                                              dm=self.dm,
                                              min_count=self.min_count,
                                              epochs=self.epochs)
        model.build_vocab(self.train_corpus)
        model.train(self.train_corpus, total_examples=model.corpus_count, epochs=model.epochs)
        if verbose:
            print("Model training complete!")
        self.model = model

    def calc_self_recognition_ability(self):
        '''Calculates the trained model's ability to recognize training documents as being most similar to themselves (across the corpus)
        CREDIT: Adapted from Gensim's Doc2Vec Tutorial https://github.com/RaRe-Technologies/gensim/blob/develop/docs/notebooks/doc2vec-lee.ipynb
        INPUT: trained model, training docs
        OUTPUT: count/rate of self-recognition (int/float), test passed (bool)
        '''
        model = self.model
        ranks = []
        second_ranks = []
        for doc_id in range(self.n_training_docs):
            doc = self.train_corpus[doc_id].words
            inferred_vector = self.model.infer_vector(doc, epochs=self.epochs)
            self.inferred_vecs['docs'].append(doc)
            self.inferred_vecs['vecs'].append(inferred_vector)
            sims = model.docvecs.most_similar([inferred_vector], topn=len(model.docvecs)) # Gives you all document tags and their cosine similarity
            rank = [docid for docid, sim in sims].index(doc_id) # Gets its own self-ranking
            ranks.append(rank)
            second_ranks.append(sims[1])
        rank_counter = collections.Counter(ranks) # Let's count how each document ranks with respect to the training corpus
        self.rank_counter = rank_counter # Results vary between runs due to random seeding and very small corpus
        self.n_self_recognized = self.rank_counter[0]
        self.self_recog_rate = self.n_self_recognized / self.n_training_docs
        self.greater_than_95 = self.self_recog_rate >= 0.95

    def calculate_pair_sims_array(self, pairings_df, is_train=True):
        '''Calculate array of the cosine similarities between inferred DocVecs of lyrics and annotations
        INPUT: lyric array, annotation array, trained Doc2Vec model
        OUTPUT: array of cosine similarities between inferred DocVecs
        '''
        ref_vecs = []
        tate_vecs = []
        rt_cs = []
        rt_ed = []
        for row in pairings_df.index:
            ref_doc = pairings_df.loc[row,['ref_pp_text']][0]
            tate_doc = pairings_df.loc[row,['tate_pp_text']][0]
            inf_ref_vec = self.model.infer_vector(ref_doc, epochs=self.epochs).reshape(-1, 1)
            inf_tate_vec = self.model.infer_vector(tate_doc, epochs=self.epochs).reshape(-1, 1)
            ref_vecs.append(inf_ref_vec)
            tate_vecs.append(inf_tate_vec)
            cs = 1 - cosine(inf_ref_vec, inf_tate_vec)
            ed = euclidean(inf_ref_vec, inf_tate_vec)
            rt_cs.append(cs)
            rt_ed.append(ed)
        calc_pairings_df = pairings_df.copy()
        calc_pairings_df['ref_vecs'] = ref_vecs
        calc_pairings_df['tate_vecs'] = tate_vecs
        calc_pairings_df['pair_cs'] = rt_cs
        calc_pairings_df['pair_ed'] = rt_ed
        is_true_pair = calc_pairings_df['is_pair'] == 1
        avg_true_pair_cs = calc_pairings_df[is_true_pair]['pair_cs'].mean()
        avg_false_pair_cs = calc_pairings_df[~is_true_pair]['pair_cs'].mean()
        max_true_pair_cs = calc_pairings_df[is_true_pair]['pair_cs'].max()
        max_false_pair_cs = calc_pairings_df[~is_true_pair]['pair_cs'].max()
        min_true_pair_cs = calc_pairings_df[is_true_pair]['pair_cs'].min()
        min_false_pair_cs = calc_pairings_df[~is_true_pair]['pair_cs'].min()
        pair_cs_stats = {'avg_tru':avg_true_pair_cs, 'avg_false':avg_false_pair_cs,
                        'max_tru':max_true_pair_cs, 'max_false':max_false_pair_cs,
                        'min_tru':min_true_pair_cs, 'min_false':min_false_pair_cs}
        avg_true_pair_ed = calc_pairings_df[is_true_pair]['pair_ed'].mean()
        avg_false_pair_ed = calc_pairings_df[~is_true_pair]['pair_ed'].mean()
        max_true_pair_ed = calc_pairings_df[is_true_pair]['pair_ed'].max()
        max_false_pair_ed = calc_pairings_df[~is_true_pair]['pair_ed'].max()
        min_true_pair_ed = calc_pairings_df[is_true_pair]['pair_ed'].min()
        min_false_pair_ed = calc_pairings_df[~is_true_pair]['pair_ed'].min()
        pair_ed_stats = {'avg_tru':avg_true_pair_ed, 'avg_false':avg_false_pair_ed,
                        'max_tru':max_true_pair_ed, 'max_false':max_false_pair_ed,
                        'min_tru':min_true_pair_ed, 'min_false':min_false_pair_ed}
        if is_train:
            self.tr_pairings_df = calc_pairings_df.copy()
            self.train_true_cs = calc_pairings_df[calc_pairings_df['is_pair'] == 1]['pair_cs']
            self.train_false_cs = calc_pairings_df[calc_pairings_df['is_pair'] == 0]['pair_cs']
            self.train_true_ed = calc_pairings_df[calc_pairings_df['is_pair'] == 1]['pair_ed']
            self.train_false_ed = calc_pairings_df[calc_pairings_df['is_pair'] == 0]['pair_ed']
            self.tr_cs_pairings_stats = pair_cs_stats
            self.tr_ed_pairings_stats = pair_ed_stats
        else:
            self.tst_pairings_df = calc_pairings_df.copy()
            self.test_true_cs = calc_pairings_df[calc_pairings_df['is_pair'] == 1]['pair_cs']
            self.test_false_cs = calc_pairings_df[calc_pairings_df['is_pair'] == 0]['pair_cs']
            self.test_true_ed = calc_pairings_df[calc_pairings_df['is_pair'] == 1]['pair_ed']
            self.test_false_ed = calc_pairings_df[calc_pairings_df['is_pair'] == 0]['pair_ed']
            self.tst_cs_pairings_stats = pair_cs_stats
            self.tst_ed_pairings_stats = pair_ed_stats

    def calc_tt_hypothesis_test(self, for_train_pairings=True, for_cs=True):
        '''Conducts two-tailed hypothesis test to determine whether true/false pair groups are statistically distinct from each other (at the 1% level)
        INPUT: array of cosine similarities between true & false pairs
        OUTPUT: t-statistic (float), p value (float), whether test is significant (bool)
        '''
        pairs_df = self.tr_pairings_df if for_train_pairings else self.tst_pairings_df
        sim_col = 'pair_cs' if for_cs else 'pair_ed'
        true_sims = pairs_df[pairs_df['is_pair'] == 1][sim_col]
        false_sims = pairs_df[pairs_df['is_pair'] == 0][sim_col]
        stat, p = ttest_ind(true_sims, false_sims)
        if for_train_pairings:
            if for_cs:
                self.cs_train_stat = stat
                self.cs_train_p_val = p
                self.cs_is_train_significant = p < 0.01
            else:
                self.ed_train_stat = stat
                self.ed_train_p_val = p
                self.ed_is_train_significant = p < 0.01
        else:
            if for_cs:
                self.cs_test_stat = stat
                self.cs_test_p_val = p
                self.cs_is_test_significant = p < 0.01
            else:
                self.ed_test_stat = stat
                self.ed_test_p_val = p
                self.ed_is_test_significant = p < 0.01

    def plot_sim_distribution(self, use_train=True, use_cs=True, save_fig=False):
        '''Plot distributions of true/false cosine similarities of pairs (red = false, blue = true)
        INPUT: array of cosine similarities between true & false pairs
        OUTPUT: plot of distributions
        '''
        if use_train:
            tru_pairs = self.train_true_cs if use_cs else self.train_true_ed
            non_pairs = self.train_false_cs if use_cs else self.train_false_ed
        else:
            tru_pairs = self.test_true_cs if use_cs else self.test_true_ed
            non_pairs = self.test_false_cs if use_cs else self.test_false_ed
        fig = plt.figure(figsize=(10,5))
        ax = fig.add_subplot(111)
        title = "Distributions of DocVec Similarity - Model:" + self.model_name
        ax.set_title(title, fontsize=18)
        plt.hist(non_pairs, bins=100, color='red', alpha=0.3, label='mismatched pairs')
        plt.hist(tru_pairs, bins=100, color='blue', alpha=0.3, label='true pairs')
        plt.axvline(x=tru_pairs.mean(), c='blue', alpha=0.6, linewidth=3)
        plt.axvline(x=non_pairs.mean(), c='red', alpha=0.6, linewidth=3)
        dist = "Cosine Similarity" if use_cs else "Euclidean Distance"
        x_label = dist + ' of Annotation & Lyric DocVectors'
        ax.set_xlabel(x_label, fontsize=16)
        ax.set_ylabel('Frequency', fontsize=16)
        ax.legend(loc='upper center', ncol=2, markerscale=0.5, bbox_to_anchor=(0.5, -0.15))
        plt.show()
        if save_fig:
            shorthand_dist = 'cs' if use_cs else 'ed'
            fig.savefig('../images/{0}_dist_{1}.png'.format(shorthand_dist, self.model_name))

class DocVecModelEvaluator(object):
    '''
    Uses Gensim's Doc2Vec model to keep track of different model variations for comparison
    '''
    def __init__(self):
        self.eval_areas_dict = {'model':0, 'self_recog_rate':0,'cs_train_p_val':0, 'cs_test_p_val':0, 'ed_train_p_val':0, 'ed_test_p_val':0, 'cs_is_train_significant':0, 'cs_is_test_significant':0, 'ed_is_train_significant':0, 'ed_is_test_significant':0, 'tr_cs_pairings_stats': 0, 'tst_cs_pairings_stats':0, 'tr_ed_pairings_stats':0, 'tst_ed_pairings_stats':0}
        self.eval_dict = dict()

    def train_new_model(self, model_name, train_corpus, train_corp_name, vector_size):
        model = Doc2VecModeler(model_name, train_corpus, train_corp_name, vector_size=vector_size)
        model.fit_model(verbose=True)
        model.calc_self_recognition_ability()
        model.calculate_pair_sims_array(train_pairings_df, is_train=True)
        model.calculate_pair_sims_array(test_pairings_df, is_train=False)
        model.calc_tt_hypothesis_test(for_train_pairings=True, for_cs=True)
        model.calc_tt_hypothesis_test(for_train_pairings=False, for_cs=True)
        model.calc_tt_hypothesis_test(for_train_pairings=True, for_cs=False)
        model.calc_tt_hypothesis_test(for_train_pairings=False, for_cs=False)
        model.plot_sim_distribution(use_train=True, use_cs=True, save_fig=True)
        model.plot_sim_distribution(use_train=False, use_cs=True, save_fig=True)
        model.plot_sim_distribution(use_train=True, use_cs=False, save_fig=True)
        model.plot_sim_distribution(use_train=False, use_cs=False, save_fig=True)
        update_stats(model)

    def update_stats(self, model):
        model_eval_stats = self.eval_areas_dict.copy()
        model_eval_stats['model'] = model
        model_eval_stats['self_recog_rate'] = model.self_recog_rate
        model_eval_stats['cs_train_p_val'] = model.cs_train_p_val
        model_eval_stats['cs_test_p_val'] = model.cs_test_p_val
        model_eval_stats['ed_train_p_val'] = model.ed_train_p_val
        model_eval_stats['ed_test_p_val'] = model.ed_test_p_val
        model_eval_stats['cs_is_train_significant'] = model.cs_is_train_significant
        model_eval_stats['cs_is_test_significant'] = model.cs_is_test_significant
        model_eval_stats['ed_is_train_significant'] = model.ed_is_train_significant
        model_eval_stats['ed_is_test_significant'] = model.ed_is_test_significant
        model_eval_stats['tr_cs_true_mean'] = model.tr_cs_pairings_stats['avg_tru']
        model_eval_stats['tr_cs_false_mean'] = model.tr_cs_pairings_stats['avg_false']
        model_eval_stats['tst_cs_true_mean'] = model.tst_cs_pairings_stats['avg_tru']
        model_eval_stats['tst_cs_false_mean'] = model.tst_cs_pairings_stats['avg_false']
        model_eval_stats['tr_ed_true_mean'] = model.tr_ed_pairings_stats['avg_tru']
        model_eval_stats['tr_ed_false_mean'] = model.tr_ed_pairings_stats['avg_false']
        model_eval_stats['tst_ed_true_mean'] = model.tst_ed_pairings_stats['avg_tru']
        model_eval_stats['tst_ed_false_mean'] = model.tst_ed_pairings_stats['avg_false']
        self.eval_dict[model.model_name] = model_eval_stats
        self.eval_cols = self.eval_dict[model.model_name].keys()

    def print_model_eval_stats(self):
        eval_df = pd.DataFrame.from_dict(self.eval_dict, orient='index', columns=self.eval_cols)
        print(eval_df)
        self.eval_df = eval_df
        return eval_df

def main():
    corpus_dict = read_in_pkl('corpus_dict')
    train_df = read_in_pkl('train_df')
    test_df = read_in_pkl('test_df')
    lookup_dicts = read_in_pkl('lookup_dicts')
    pcorpuses = read_in_pkl('pcorpuses')
    train_pairings_df = read_in_pkl('train_pairings_df')
    test_pairings_df = read_in_pkl('test_pairings_df')

    artists = lookup_dicts[0]
    doc_rt_train_dict = lookup_dicts[1]
    doc_rt_test_dict = lookup_dicts[2]
    rt_doc_train_dict = lookup_dicts[3]
    rt_doc_test_dict = lookup_dicts[4]
    rt_in_train_dict = lookup_dicts[5]
    artist_rt_dict = lookup_dicts[6]
    rt_artist_dict = lookup_dicts[7]
    song_rt_dict = lookup_dicts[8]
    rt_song_dict = lookup_dicts[9]
    song_id_to_title_dict = lookup_dicts[10]

    ref_train_pcorpus = pcorpuses[0]
    ref_test_pcorpus = pcorpuses[1]
    tate_train_pcorpus = pcorpuses[2]
    tate_test_pcorpus = pcorpuses[3]
    rt_train_pcorpus = pcorpuses[4]
    rt_test_pcorpus = pcorpuses[5]
    rt_tagged_train_pcorpus = pcorpuses[6]
    rt_tagged_test_pcorpus = pcorpuses[7]

    model_specs = {'training_corpus':[ref_train_pcorpus, tate_train_pcorpus, rt_train_pcorpus, rt_tagged_train_pcorpus],
                    'vector_size':[50, 100, 200],
                    'window':[3, 5, 7],
                    'epochs':[25, 50, 110]}

    doc_eval = DocVecModelEvaluator()

    doc_eval.train_new_model('r_50', ref_train_pcorpus, 'r_tr', vector_size=50)
    doc_eval.train_new_model('r_100', ref_train_pcorpus, 'r_tr', vector_size=100)
    doc_eval.train_new_model('r_200', ref_train_pcorpus, 'r_tr', vector_size=200)

    doc_eval.train_new_model('t_50', tate_train_pcorpus, 't_tr', vector_size=50)
    doc_eval.train_new_model('t_100', tate_train_pcorpus, 't_tr', vector_size=100)
    doc_eval.train_new_model('t_200', tate_train_pcorpus, 't_tr', vector_size=200)

    doc_eval.train_new_model('rt_50', rt_train_pcorpus, 'rt_tr', vector_size=50)
    doc_eval.train_new_model('rt_100', rt_train_pcorpus, 'rt_tr', vector_size=100)
    doc_eval.train_new_model('rt_200', rt_train_pcorpus, 'rt_tr', vector_size=200)

    doc_eval.train_new_model('rt_tagged_50', rt_tagged_train_pcorpus, 'rt_tagged_tr', vector_size=50)
    doc_eval.train_new_model('rt_tagged_100', rt_tagged_train_pcorpus, 'rt_tagged_tr', vector_size=100)
    doc_eval.train_new_model('rt_tagged_200', rt_tagged_train_pcorpus, 'rt_tagged_tr', vector_size=200)

    eval_df = doc_eval.print_model_eval_stats()

    eval_df.to_csv('../data/eval_df.csv')

if __name__ == '__main__':
    main()
