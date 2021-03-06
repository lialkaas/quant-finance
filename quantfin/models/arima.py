#  MIT License
#
#  Copyright (c) 2019 Oleksii Lialka
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.


import warnings
from itertools import product

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.tsa.api as smt
from tqdm import tqdm_notebook

warnings.filterwarnings('ignore')

# Default path to ARIMA config files
config_path = './configs/sarima/'


def optimize(series, p, d, q, ps, ds, qs, s, display=True):
    """
        Return optimized parameters of ARIMA(p, d, q)x(P, D, Q, s)
        Save results converging parameters with corresponding AIC to file
        parameters_list - list with (p, d, q)x(P, D, Q, s) tuples
    """

    parameters_list = list(product(p, q, ps, qs))

    results = []
    best_aic = float("inf")
    iter_sum = len(parameters_list)
    iter_done = 0

    if display:
        display_header = True

    for param in tqdm_notebook(parameters_list):
        if display_header:
            print('\nNumber of combinations =', iter_sum)
            print('\n{:<12} | {:^12} | {:^12}'.format('(p, q, P, Q)', 'AIC', 'Iteration'))
            display_header = False
        iter_done += 1

        try:
            arima = sm.tsa.statespace.SARIMAX(series, order=(param[0], d, param[1]),
                                              seasonal_order=(param[2], ds, param[3], s))
            model = arima.fit(disp=-1)
        except:
            continue

        aic = model.aic
        # saving best model, AIC and parameters
        if aic < best_aic:
            best_aic = aic
            if display:
                print(param, '| {:^12.2f} |{:>6}/{:<6}'.format(aic, iter_done, iter_sum))
        results.append([param, model.aic])

    result_table = pd.DataFrame(results)
    result_table.columns = ['parameters', 'aic']

    # sorting in ascending order, the lower AIC is - the better
    result_table = result_table.sort_values(by='aic', ascending=True).reset_index(drop=True)
    p, q, ps, qs = result_table.parameters[0]


    print('\nOptimized ARIMA({}, {}, {})x({}, {}, {}, {})\n'
          .format(p, d, q, ps, ds, qs, s))
    return p, q, ps, qs


def seasonality(series, par_range=100, lags=60, optimize=True, graph=False):
    """
        Plot time series, its ACF and PACF, calculate Dickey–Fuller test
        lags - how many lags to include in ACF, PACF calculation
    """
    # Remove trend (non-seasonal differences), make data stationary
    if optimize:
        d = 0
        p_value_best = 0.0001
        for d in range(par_range):
            data_stat = series - series.shift(d)
            p_value = sm.tsa.stattools.adfuller(data_stat[d:])[1]
            if p_value_best > p_value:
                p_value_best = p_value
                d_best = d
                break
        d = d_best
        print('Non-seasonal integral d =', d)

    # Remove seasonality
    if optimize:
        ds = 0
        s_best = 0
        acf_best = float("inf")
        for s in range(par_range):
            data_stat = series - series.shift(d + s)
            acf = np.mean(sm.tsa.stattools.acf(data_stat[d + s:]))
            if acf_best > acf:
                acf_best = acf
                s_best = s
        s = s_best
        if s > 0:
            ds = 1
        print('Season length s =', s)

    data_stat = series - series.shift(d + s)
    p_value = sm.tsa.stattools.adfuller(data_stat[d + s:])[1]

    if graph:
        with plt.style.context('bmh'):
            plt.figure(figsize=(10, 5))
            layout = (2, 2)
            ts_ax = plt.subplot2grid(layout, (0, 0), colspan=2)
            acf_ax = plt.subplot2grid(layout, (1, 0))
            pacf_ax = plt.subplot2grid(layout, (1, 1))

            data_stat[d + s:].plot(ax=ts_ax)

            ts_ax.set(title="TSA Plots\n Dickey-Fuller: p={0:.5f}".format(p_value))
            smt.graphics.plot_acf(data_stat[d + s:], lags=lags, ax=acf_ax)
            smt.graphics.plot_pacf(data_stat[d + s:], lags=lags, ax=pacf_ax)
            plt.tight_layout()
            plt.show()
    return d, ds, s


def predict(data, result, n_predict, graph=False):
    predict = result.get_prediction(dynamic=len(data) - n_predict)
    predict_ci = predict.conf_int()

    if graph:
        # Plot predictions against actual data
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set(title='Predictions of ARIMA')
        # Plot actual data
        data.plot(ax=ax, label='Actual')
        # Plot predictions
        predict.predicted_mean[10:].plot(ax=ax, style='r', label='One-step-ahead prediction')
        pci = predict_ci[10:]
        ax.fill_between(pci.index, pci.iloc[:, 0], pci.iloc[:, 1], color='r', alpha=0.1)
        ax.legend(loc='lower right')
        plt.grid(True)
        plt.axis('tight')
        plt.show()
    return predict


def error(data, predict, graph=False):
    predict_error = np.abs((data[10:] / predict.predicted_mean[10:]) - 1) * 100
    predict_error_ma = np.mean(predict_error)
    if graph:
        # Graph error
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set(title='Mean absolute error = {:4.2f}%'.format(predict_error_ma), ylabel='error, %')
        # In-sample one-step-ahead predictions
        predict_error.plot(ax=ax, label='One-step-ahead prediction error')
        plt.axis('tight')
        plt.show()
    return predict_error_ma


def main():
    # Import data
    path = '../data/^GSPC.csv'
    series = pd.read_csv(path, index_col=['Date'], skiprows=range(1, 2000), parse_dates=['Date'])
    data = series['Adj Close']

    # Remove trend and seasonality, find optimal (d, ds, s)
    d, ds, s = seasonality(data, optimize=True, graph=True)

    # Out-of-sample num of periods to forecast
    n_predict = 2

    # Initialize ranges of SARIMA parameters
    p = range(5)
    q = range(5)

    if ds == 0:
        ps, qs = [0], [0]
    else:
        ps = range(3)
        qs = range(3)

    # Optimize model
    p, q, ps, qs = optimize(data, p, d, q, ps, ds, qs, s, display=True)

    # Build optimal ARIMA model
    model = sm.tsa.statespace.SARIMAX(data, order=(p, d, q), seasonal_order=(ps, ds, qs, s))
    result = model.filter(model.fit(disp=False).params)
    result.summary()

    # Make one-step-ahead prediction
    # Plot predictions against actual data
    prediction = predict(data, result, n_predict, graph=True)

    # Estimate prediction error
    mean_abs_error = error(data, prediction, graph=True)


if __name__ == '__main__':
    main()
