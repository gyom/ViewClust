from datetime import datetime
import numpy as np
import pandas as pd
from viewclust.target_series import target_series

def job_use(jobs, d_from, target, d_to='', use_unit='cpu',
            serialize_queued='', serialize_running='', serialize_dist=''):
    """Takes a DataFrame full of job information and returns usage based on specified unit.

    This function operates as a stepping stone for plotting usage figures
    and returns various series and frames for several different uses.

    Parameters
    -------
    jobs: DataFrame
        Job DataFrame typically generated by the ccmnt package.
    use_unit: str, optional
        Usage unit to examine. One of: {'cpu', 'cpu-eqv', 'gpu', 'gpu-eqv'}.
        Defaults to 'cpu'.
    d_from: date str
        Beginning of the query period, e.g. '2019-04-01T00:00:00'.
    target: int-like
        Typically a cpu allocation or core eqv value for a particular acount, often 50.
    d_to: date str, optional
        End of the query period, e.g. '2020-01-01T00:00:00'. Defaults to now if empty.
    debugging: boolean, optional
        Boolean for reporting progress to stdout. Default False.
    serialize_running, serialize_queued, serialize_dist: str, optional
        Pickles given structure with argument as a name. If left empty, pickle procedure is skipped.
        Defaults to empty.

    Returns
    -------
    clust:
        Frame of system info at given time intervals.
        Typically referenced by other functions for plotting information.
    queued:
        Frame of queued resources
    running:
        Frame of running resources
    dist_from_target:
        Series for delta plots
    """

    # d_to boilerplate
    if d_to == '':
        d_to = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    jobs = jobs.sort_values(by=['submit'])

    if use_unit == 'cpu':
        jobs['use_unit'] = jobs['reqcpus']
    elif use_unit == 'cpu-eqv':
        jobs['mem_scale'] = jobs['mem'] / 4096.0
        jobs['use_unit'] = jobs[['mem_scale', 'reqcpus']].max(axis=1)
    elif use_unit == 'gpu':
        # If erroring from elasticsearch double check column names
        # Other thing to check: if reqgres has things other than gpu reqs in it
        print('Warning! : some jobs may not have proper gpu reqtres/reqgres')
        try:
            raise ValueError('Currently unstable. Uncomment exception at own risk.')
            jobs['ngpus'] = jobs['reqgres'].str.extract(r'gpu:(\d+)').astype('float')
        except KeyError:
            # This is the elastic search one here:
            print('Warning: compatability issue for column names needs to be fixed.')
            jobs['ngpus'] = jobs['reqtres'].str.extract(r'gpu=(\d+)').astype('float')

        jobs['use_unit'] = jobs['ngpus']
    else:
        print('Warning: some jobs may not have proper gpu reqtres/reqgres')
        print('gpu equiv to be supported soon')
        return

    jobs_submit = jobs.copy()
    jobs_submit.index = jobs_submit['submit']
    jobs_start = jobs.copy()
    jobs_start.index = jobs_start['start']
    jobs_end = jobs.copy()
    jobs_end.index = jobs_end['end']

    queued = jobs_submit.groupby(pd.Grouper(freq='H')).sum()['use_unit'].fillna(0) \
            .subtract(jobs_start.groupby(pd.Grouper(freq='H')).sum()['use_unit'] \
            .fillna(0), fill_value=0).cumsum()
    running = jobs_start.groupby(pd.Grouper(freq='H')).sum()['use_unit'].fillna(0) \
            .subtract(jobs_end.groupby(pd.Grouper(freq='H')).sum()['use_unit'] \
            .fillna(0), fill_value=0).cumsum()

    # Target: If int, calculate it, else use the variable passed (should be a series)
    clust = pd.DataFrame()
    if isinstance(target, int):
        clust = target_series([(d_from, d_to, target)])
    else:
        clust = target

    sum_target = np.cumsum(clust)
    sum_running = np.cumsum(running)

    # New workaround for job record problems
    sum_target = sum_target.loc[d_from:d_to]

    sum_running.index.name = 'datetime'
    sum_running = sum_running.loc[d_from:d_to]

    dist_from_target = (sum_running - sum_target)

    if serialize_running != '':
        running.to_pickle(serialize_running)
    if serialize_queued != '':
        queued.to_pickle(serialize_queued)
    if serialize_dist != '':
        dist_from_target.to_pickle(serialize_dist)

    return clust, queued, running, dist_from_target
