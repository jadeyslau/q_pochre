import pandas as pd, numpy as np, re

from numpy import asarray, power, log
from scipy.stats.mstats import gmean

import seaborn as sns

class Data:
    def __init__(self, data_path, fname_arr, ref_gene, bio_ref, treated=True):
        self.data_path = data_path
        self.fname_arr = fname_arr
        self.ref_gene  = ref_gene
        self.bio_ref  = bio_ref
        self.treated   = treated

    log2 = lambda self,x: log(x)/log(2)

    def load_csv(self):
        # Reads multiple csv files. Input path of file and
        # array of filenames assuming they are in the same folder. Output a list of dataframes.
        df_list = []
        for i, df_name in enumerate(self.fname_arr):
            fname  = self.data_path+df_name+'.csv'
            df = pd.read_csv(fname, header=0)
            df['Plate'] = i+1
            df_list.append(df)
        return df_list

    def raw_data(self):
        return self.load_csv()

    #--------------------------------------------------------------------------------
    # Just a bunch of housekeeping functions to tidy and prepare raw LightCycler data

    def tidy_each_experiment(self):
        df_list = self.load_csv()
        tidied  = []
        for df in df_list:
            t_df = self.tidy(df)
            tidied.append(t_df)
        return tidied

    def tidy(self,df):

        df = self.trim_all_columns(df)

        if 'Plate' not in df.columns: df['Plate'] = 'NaN'

        df = self.remove_columns(df)
        df = self.rename_columns(df)
        df = df.replace(regex=r'-', value=0)

        df['Cq'] = pd.to_numeric(df['Cq'])

        if self.treated: df['Treatment'] = df['Treatment'].str.title()

        df = self.add_columns(df)

        # Set value to 0 if Cq is >= 40
        df['Cq'].where(df['Cq'] < 40, 0, inplace=True)

        # Reorder columns
        columns_titles = ['Sample','Bio Rep', 'Target', 'Cq', 'Cq Mean', 'Replicate Group', 'Condition', 'Treatment', 'Plate']
        df = df[columns_titles]
        return df

    def trim_all_columns(self,df):
        """
        Trim whitespace from ends of each value across all series in dataframe
        """

        #Remove whitespace around column headers if any.
        df.rename(columns=lambda x: x.strip(),inplace = True)

        trim_strings = lambda x: x.strip() if isinstance(x, str) else x
        return df.applymap(trim_strings)

    def remove_columns(self,df):
        #Remove extraneous columns generated by LightCycler export. Columns that are retained are commented out.
        df = df.drop(['Color',
         'Position',
        #  'Sample Name',
        #  'Gene Name',
        #  'Condition Name',
        #  'Cq',
        #  'Cq Mean',
         'Cq Error',
         'Excluded',
         'Sample Type',
         'Sample Type RQ',
         'Gene Type',
         'Condition Type',
        #  'Replicate Group',
         'Ratio',
         'Ratio Error',
         'Normalized Ratio',
         'Normalized Ratio Error',
         'Scaled Ratio',
         'Scaled Ratio Error',
         'Dye',
         'Edited Call',
         'Failure',
         'Slope',
         'EPF',
         'Notes',
         'Sample Prep Notes',
         'Number'
         #,'Plate'
          ], axis=1)
        return df

    def rename_columns(self,df):
        """
        This function renames columns 'Sample Name', 'Gene Name' to 'Sample' and 'Target' respectively.
        :return: Updated df
        :rtype: DataFrame
        """
        df       = df.rename(columns={'Sample Name':'Sample','Gene Name': 'Target', 'Condition Name': 'Treatment'})
        return df

    def add_columns(self,df):
        # Add column to define condition
        sample_condition = asarray([re.sub("[^A-Z\d]", "", re.search("^[^_]*", i).group(0).upper()) for i in df['Sample']])
        df['Condition'] = sample_condition

        # Add column to define bio replicate number
        # Old data does not have bio reps so if it doesn't (according to sample name) then bio rep set as 0
        if re.search(r'([-\d]$)', df['Sample'][0]):
            sample_bio_rep = asarray([re.sub("[^A-Z\d]", "", re.search(r'([-\d]$)', i).group(0).upper()) for i in df['Sample']])
        else:
            sample_bio_rep = asarray([0 for i in df['Sample']])

        df['Bio Rep'] = sample_bio_rep
        return df

#--------------------------------------------------------------------------------
# Analysing Cq data
    '''
    1. average tech reps
    2. normalise to bactin - dct from each sample (bio duplicate) - sample control
    3. get relative expression for each sample
    4. take mean of rq of bio replicates
    5. fold change relative to biological control (1A?) - i.e. normalise again to day 3 1A non gravel - plot this.

    '''

    # analyse here

    def get_ref_data(self,df,relevant_cols,relevant_grps):

        # select relevant columns from reference gene data and find mean of technical replicates
        ref_target_df             = df.loc[df['Target'] == self.ref_gene, relevant_cols]
        ref_target_grouped_by_age = ref_target_df.groupby(relevant_grps)
        ref_target_mean_by_sample = ref_target_grouped_by_age.agg(self.amean_cq)
        ref_target_mean_by_treat  = ref_target_mean_by_sample.groupby(['Treatment','Condition']).agg(self.amean_cq)

        return ref_target_mean_by_sample, ref_target_mean_by_treat

    def get_ref_mean(self, ref_mean_df, age, biorep, treatment):
        ref_mean_by_age = ref_mean_df.loc[[age, 'amean_cq']].reset_index()
        ref_mean_cq     = ref_mean_by_age[(ref_mean_by_age['Bio Rep'] == biorep) & (ref_mean_by_age['Treatment'] == treatment)]
        return ref_mean_cq

    def ddcq(self, ref_mean_cq, sample_mean_cq):
        dcq  = ref_mean_cq - sample_mean_cq
        ddcq = float(power(2, dcq))
        return ddcq

    def amean_cq(self,seq):
        amean_cq = np.mean(seq)
        return amean_cq

    def gmean_cq(self,seq):
#         print(seq)
        gmean_cq = gmean(seq)
        return gmean_cq

    def concat_df(self,df_arr):
        # Concatenates dataframes given as an list.
        concatenated = pd.concat(df_arr, sort=False)
        return concatenated

#--------------------------------------------------------------------------------------------
    def calculate_mean_cq(self,df,ref_sample_grouped_by_age,ref_target_mean_by_sample):
        # define conditions and initiate empty array and df
        unique_cond = df.Condition.unique()
        mean_cq_df       = pd.DataFrame({
                                   'Sample'   : [],
                                   'Bio Rep'  : [],
                                   'Target'   : [],
                                   'Age'      : [],
                                   'Mean Cq'  : [],
                                   'Treatment': []
                                  })

        # iterate through unique 'conditions' i.e. ages and NEG, calculate relative quantity, and
        for condition, group in ref_sample_grouped_by_age:
            for age in unique_cond:
                if age == condition[0]:
                    sample         = condition[1]
                    biorep         = group['Bio Rep'].unique()[0]
                    treatment      = group['Treatment'].unique()[0]

                    ref_mean_cq    = self.get_ref_mean(ref_target_mean_by_sample, age, biorep, treatment)['Cq']
                    sample_mean_cq = self.amean_cq(group['Cq']) # arithmetic mean of tech reps


                    # Normalise to reference gene and
                    # RQ = self.ddcq(ref_mean_cq, sample_mean_cq)

                    mean_cq_df = mean_cq_df.append({
                                           'Sample'   : sample,
                                           'Bio Rep'  : biorep,
                                           'Target'   : group['Target'].unique()[0],
                                           'Age'      : age,
                                           'Mean Cq'  : sample_mean_cq,
                                           'Treatment': treatment
                                         },ignore_index=True)

        return mean_cq_df

    def calculate_RQ(self):
        """Description
        :param DataFrame sample_frame: A sample data frame.
        :param string ref_target: A string matching an entry of the Target column; reference gene;
            the target to use as the reference target (e.g. 'BACTIN')
        :return: A DataFrame with columns: Sample, Target, Age, DeltaCq, and Rel Exp.
        :rtype: DataFrame
        """
        df       = self.tidy_each_experiment()
        if len(df) > 1: df = self.concat_df(df)

        ref_gene = self.ref_gene
        relevant_cols = ['Sample', 'Cq', 'Condition', 'Bio Rep', 'Plate']
        relevant_grps = ['Condition', 'Sample', 'Bio Rep','Plate']
        if self.treated: relevant_cols.append('Treatment'); relevant_grps.append('Treatment')

        if isinstance(df,type(list)): df = df[0] #if only one plate

        ref_target_mean_by_sample, ref_target_mean_by_treat = self.get_ref_data(df, relevant_cols, relevant_grps)

        ref_sample_grouped_by_age = df.groupby(relevant_grps)

        mean_cq_df = self.calculate_mean_cq(df,ref_sample_grouped_by_age,ref_target_mean_by_sample).sort_values(['Age', 'Target', 'Treatment'])

        # Control group Avg Cq per Target
        return mean_cq_df

    def normalise_to_bio_ref(self):
        # normalisation factor is the experimentally relevant group such as untreated control
        # or a particular target gene that your final results will be relative to
#         rq_df_no_refgene = rq_df.groupby(['Target', 'Age', 'Treatment']).agg(self.amean_cq).reset_index()

        rq_df            = self.calculate_RQ()
        rq_df_no_refgene = rq_df[rq_df.Target != 'BACTIN']
#         rq_df_no_refgene = rq_df

        nf_age           = self.bio_ref[0]
        nf_target        = self.bio_ref[1]
        get_nf_untreated = rq_df_no_refgene[(rq_df_no_refgene['Age'] == nf_age) & (rq_df_no_refgene['Target'] == nf_target) & (rq_df_no_refgene['Treatment'] == 'Non Gravel')].reset_index()
        get_nf_treated   = rq_df_no_refgene[(rq_df_no_refgene['Age'] == nf_age) & (rq_df_no_refgene['Target'] == nf_target) & (rq_df_no_refgene['Treatment'] == 'Gravel')].reset_index()
        avg_RQs          = rq_df_no_refgene['RQ']

        n_bio_reps         = len(rq_df['Bio Rep'].unique())

        nf_untreated = get_nf_untreated['Treatment'][0]
        nf_treated   = get_nf_treated['Treatment'][0]

#         print(get_nf_untreated, get_nf_treated)

#         print(rq_df_no_refgene)


        norm_df = pd.DataFrame({
                                'Target'      : [],
                                'Sample'      : [],
                                'Age'         : [],
                                'Treatment'   : [],
                                'norm_RQ'     : [], # A
                                'log(norm_RQ)': [], # B
#                                 'norm_RQ_mean': [], # C
#                                 'log(norm_RQ_mean)': [], # D
#                                 'SD(log(norm_RQ))': [], # E
                               })

        for i, sample in rq_df_no_refgene.iterrows():
            sample_RQ = sample['RQ']
            sample_biorep = int(sample['Bio Rep'])

            # If the sample has been treated then compare with treated normalisation factor average
            if sample['Treatment'] == nf_untreated:
                n_RQ = sample_RQ/get_nf_untreated['RQ'][sample_biorep-1]

            elif sample['Treatment'] == nf_treated:
                n_RQ = sample_RQ/get_nf_treated['RQ'][sample_biorep-1]

            log2_norm_exp = self.log2(n_RQ)

            norm_df = norm_df.append({
                                    'Target'      : sample['Target'],
                                    'Sample'      : sample['Sample'],
                                    'Age'         : sample['Age'],
                                    'Treatment'   : sample['Treatment'],
                                    'norm_RQ'     : n_RQ, # A
                                    'log(norm_RQ)': log2_norm_exp, # B
#                                     'norm_RQ_mean': [], # C
#                                     'log(norm_RQ_mean)': [], # D
#                                     'SD(log(norm_RQ))': [], # E
                                    },ignore_index=True)


        # Bio group expression gmean of
#         temp_df['new_column'] = temp_df.groupby(['Target', 'Age', 'Treatment']).agg(self.gmean_cq).reset_index()
        norm_df_mean = norm_df.groupby(['Target', 'Age', 'Treatment']).agg({'norm_RQ': 'mean' }).reset_index()
#         print(norm_df,norm_df_mean)
        sd_df = self.calculate_sd_sem(norm_df)
#         print(sd_df)

        return norm_df, norm_df_mean

    def calculate_sd_sem(self, norm_df):
#         norm_df = self.normalise_to_bio_ref()[0]
        sd_df = norm_df.groupby(['Target', 'Age', 'Treatment']).sem() #agg({'log(norm_RQ)': 'sem' })
        return sd_df

#-------------------------------------------------------------------------------------------
# Plotting functions

    def plot_raw_cq(self):
        df = self.tidy_each_experiment()
        if len(df) > 1: df = self.concat_df(df)

        sns.set(context='paper', style='whitegrid', palette="ch:7.1,-.2,dark=.3", font='sans-serif', font_scale=1.5, color_codes=True, rc=None)
        g = sns.catplot(x="Target", y="Cq", col="Condition", hue='Treatment', hue_order=['Non Gravel','Gravel'], data=df, saturation=.5, kind="bar", ci='sd', aspect=.6)
        (g.set_axis_labels("", "Cq").set_xticklabels(rotation=45).set_titles("{col_name}").despine(left=True))
        return g

    def plot_RQ(self):
        df = self.tidy_each_experiment()
        df = self.strip_controls(self.calculate_RQ())

        sns.set(context='paper', style='whitegrid', palette="ch:7.1,-.2,dark=.3", font='sans-serif', font_scale=1.5, color_codes=True, rc=None)
        g = sns.catplot(x="Target", y="RQ", col="Age", hue='Treatment', hue_order=['Non Gravel','Gravel'], data=df, saturation=.5, kind="bar", ci='sd', aspect=.6)
        (g.set_axis_labels("", "RQ").set_xticklabels(rotation=45).set_titles("{col_name}").despine(left=True))
        return g

    def plot_norm_RQ(self):
        df = self.tidy_each_experiment()
        df = self.strip_controls(self.normalise_to_bio_ref()[1])
#         df = df.loc[(df['Target'] == 'GRIN2AB')]

        sns.set(context='paper', style='whitegrid', palette="ch:7.1,-.2,dark=.3", font='sans-serif', font_scale=1.5, color_codes=True, rc=None)
        g = sns.catplot(x="Target", y="norm_RQ", col="Age", hue='Treatment', hue_order=['Non Gravel','Gravel'], data=df, saturation=.5, kind="bar", ci='sd', aspect=.6)
        (g.set_axis_labels("", "Normalised Fold Expression").set_xticklabels(rotation=45).set_titles("{col_name}").despine(left=True))
        return g

    def strip_controls(self,df):
        stripped = df.loc[(df['Target'] != 'BACTIN') & (df['Age'] != 'NEG')]
        sort_d   = stripped.sort_values(['Target','Age','Treatment']).reset_index(drop=True)
        return sort_d

#     def hide_1A_1B(self,df):
#         df_zoom = df.loc[(df['Target'] != 'GRIN1A') & (df['Target'] != 'GRIN1B')]
#         return df_zoom
