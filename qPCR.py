import pandas as pd, numpy as np
import re

from os import path
from numpy import mean, std, power, asarray, log

# import seaborn as sns
# import matplotlib.pyplot as plt

from math import isnan
# from numpy import mean, std, power, asarray, log

from scipy import stats
from scipy.stats.mstats import gmean

#df housekeeping functions

def rename_columns(df):
    """
    This function renames columns 'Sample Name', 'Gene Name' to 'Sample' and 'Target' respectively.
    :return: Updated df
    :rtype: DataFrame
    """
    df       = df.rename(columns={'Sample Name':'Sample','Gene Name': 'Target', 'Condition Name': 'Treatment'})
    return df

def trim_all_columns(df):
    """
    Trim whitespace from ends of each value across all series in dataframe
    """
    trim_strings = lambda x: x.strip() if isinstance(x, str) else x
    return df.applymap(trim_strings)

def tidy_df(df, treatment=False):
    """
    This function performs some rudimentary housekeeping on the raw Lightcycler exported data.
    It removes trailing whitespace in column headers, removes extraneous columns, renames columns as per rename_column,
    finds and replaces '-' with numeric 0, ensures that the Cq column contain integers,
    and moves the 'Condition Name' column to the end of the df.
    :param DataFrame df: Sample DataFrame
    :param Boolean treatment: If the experiment involved some extra variable such as gravel/non gravel then pass True
    :return: Tidied df
    :rtype: DataFrame
    """
    #Remove whitespace around column headers if any.
    df.rename(columns=lambda x: x.strip(),inplace = True)

    df = trim_all_columns(df)

    if 'Plate' not in df.columns: df['Plate'] = 'NaN'

    #Remove extraneous columns generated by LightCycler export. Columns that are retained are commented out.
    df = df.drop(['Color',
     'Position',
    #  'Sample Name',
    #  'Gene Name',
    #  'Condition Name',
    #  'Cq',
    #  'Cq Mean',
    #  'Cq Error',
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
    #  'Slope',
     'EPF',
     'Notes',
     'Sample Prep Notes',
     'Number'
     #,'Plate'
      ], axis=1)

    df       = rename_columns(df)
    df       = df.replace(regex=r'-', value=0)
    df['Cq'] = pd.to_numeric(df['Cq'])

    if treatment: df['Treatment'] = df['Treatment'].str.title()

    # Add column to define condition
    sample_condition = asarray([re.sub("[^A-Z\d]", "", re.search("^[^_]*", i).group(0).upper()) for i in df['Sample']])
    df['Condition'] = sample_condition

#     df.loc[df.Cq > 40, x]= 0
    df['Cq'].where(df['Cq'] < 40, 0, inplace=True)

    #change the order of columns
    columns_titles = ['Sample', 'Target', 'Cq', 'Cq Mean', 'Cq Error', 'Replicate Group', 'Slope', 'Condition', 'Treatment', 'Plate']
    df = df[columns_titles]
    return df

# log2 = lambda x: log(x)/log(2)

def average_cq(seq, efficiency=1.0):
    """
    This function converts the Ct values into expression levels, averages them, and
    then converts the average expression levels into average Ct values.

    Given a set of Cq values, return the Cq value that represents the
    average expression level of the input.
    The intent is to average the expression levels of the samples,
    since the average of Cq values is not biologically meaningful.
    :param iterable seq: A sequence (e.g. list, array, or Series) of Cq values.
    :param float efficiency: The fractional efficiency of the PCR reaction; i.e.
        1.0 is 100% efficiency, producing 2 copies per amplicon per cycle.
    :return: Cq value representing average expression level
    :rtype: float
    """
    denominator = sum( [pow(2.0*efficiency, -Ci) for Ci in seq] )
    # print(denominator)
    # Make sure values passed in seq are ints
    avg_cq = log(len(seq)/denominator)/log(2.0*efficiency)
    return avg_cq

# list1 = [23.94,23.7,23.48]
# # list2 = [17.01,16.84,15.88]
# average_cq(list1)
# np.mean(list1)

def sem_cq(seq):
    sem = stats.sem(seq)
    return sem
def sd_cq(seq):
    sd = np.std(seq)
    return sd

def deltacq(seq, efficiency = 1.0):
#     rq_per_sample = [pow(2.0*efficiency, -Ci) for Ci in seq]
    rq_per_sample = seq
    avgcq         = average_cq(seq, efficiency=1.0)
    dcq           = avgcq - rq_per_sample
    print(rq_per_sample, avgcq, dcq)

# list1 = [23.94,23.7,23.48]
# list2 = [17.01,16.84,15.88]
# average_cq(list1)
# deltacq(list1)

def rel_expression_ddcq(sample_frame, ref_target):
#     print('Treatment = ',treatment)
    """Calculates expression of samples in a sample data frame relative to a
    single reference gene using the ∆∆Cq method.

    :param DataFrame sample_frame: A sample data frame.
    :param string ref_target: A string matching an entry of the Target column;
        the target to use as the reference target (e.g. 'BACTIN')
    :return: A DataFrame with columns: Sample, Target, Age, DeltaCq, and Rel Exp.
    :rtype: DataFrame
    """

    if len(sample_frame['Treatment'].unique()) == 1:
        print('Treatment = NaN')
        ref_target_df                = sample_frame.loc[sample_frame['Target'] == ref_target, ['Sample', 'Cq', 'Condition']]
        ref_target_grouped_by_age    = ref_target_df.groupby(['Condition', 'Sample'])
        ref_sample_df_grouped_by_age = sample_frame.groupby(['Condition', 'Sample'])
    else:
        ref_target_df                = sample_frame.loc[sample_frame['Target'] == ref_target, ['Sample', 'Cq', 'Condition', 'Treatment']]
        ref_target_grouped_by_age    = ref_target_df.groupby(['Condition', 'Sample', 'Treatment'])
        ref_sample_df_grouped_by_age = sample_frame.groupby(['Condition', 'Sample', 'Treatment'])

    ref_target_stats_by_sample   = ref_target_grouped_by_age['Cq'].aggregate([average_cq, sem_cq, sd_cq])

    unique_conditions = sample_frame.Condition.unique()
    sample_dcq_series = []
    new_df = pd.DataFrame({'Sample': [],
                           'Target': [],
                           'Age': [],
                           'DeltaCq': [],
                           'Rel Exp': [],
                           'Treatment': []
                          })


    # Iterates through unique 'conditions' i.e. ages and NEG
    for condition, group in ref_sample_df_grouped_by_age:
        for age in unique_conditions:
            if age == condition[0]:
                sample         = condition[1]
                ref_gene_cq    = ref_target_stats_by_sample.loc[age]['average_cq'][0]
                ref_gene_sd    = ref_target_stats_by_sample.loc[age]['sd_cq'][0]

                # mean_by_sample = group['Cq'].agg(average_cq)
                mean_by_sample = group['Cq'].agg(np.mean)
                sem_by_sample  = sem_cq(group['Cq'])
                sd_by_sample   = sd_cq(group['Cq'])
                print(mean_by_sample, 'end')
#                 sample_dcq     = mean_by_sample - ref_gene_cq
#                 sample_dcq_sd  = sd_by_sample - ref_gene_sd
#                 rel_exp     = power(2, -sample_dcq)
#                 rel_exp_sd  = power(2, -sample_dcq_sd)

                sample_dcq     = ref_gene_cq - mean_by_sample
                sample_dcq_sd  = ref_gene_sd - sd_by_sample

                rel_exp     = power(2, sample_dcq)
                rel_exp_sd  = power(2, sample_dcq_sd)
#                 rel_exp needs to be sample_dcq - ref_gene_dcq?

#                 print(sample, sample_dcq, rel_exp)
                new_df = new_df.append({'Sample': sample,
                           'Target': group['Target'].unique()[0],
                           'Age': age,
                           'DeltaCq': sample_dcq,
                           'Rel Exp': rel_exp,
                           'Rel Exp SD': rel_exp_sd,
                           'Treatment': group['Treatment'].unique()[0]}
                             ,ignore_index=True)

#     new_df.to_csv(path+fname+'_analysed.csv', index = None, header=True)
    return new_df


# testdf          = df
# print(df)
# df_relexp       = rel_expression_ddcq(testdf, 'BACTIN')
# df_exclude_negs = df_relexp.loc[(df_relexp['Target'] != 'BACTIN') & (df_relexp['Condition'] != 'NEG')]

# norm to bacin then grin1a?
