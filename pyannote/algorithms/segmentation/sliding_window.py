#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2012-2014 CNRS (Hervé BREDIN - http://herve.niderb.fr)

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import unicode_literals

import itertools
import numpy as np
import scipy.signal

from pyannote.core import Timeline
from pyannote.core.segment import Segment, SlidingWindow
from ..stats.gaussian import Gaussian


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


class SlidingWindowsSegmentation(object):
    """

    <---d---><-g-><---d--->
    [   L   ]     [   R   ]
         [   L   ]     [   R   ]
    <-s->

    Parameters
    ----------
    duration : float, optional
        Set left/right window duration. Defaults to 1 second.
    step : float, optional
        Set step duration. Defaults to 100ms
    gap : float, optional
        Set gap duration. Defaults to no gap (i.e. 0 second)
    """

    def __init__(self, duration=1.0, step=0.1, gap=0.0, threshold=0., **kwargs):
        super(SlidingWindowsSegmentation, self).__init__()
        self.duration = duration
        self.step = step
        self.gap = gap
        self.threshold = threshold

        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def diff(self, left, right, feature):
        raise NotImplementedError()

    def iterdiff(self, feature):
        """(middle, difference) generator

        `middle`
        `difference`


        Parameters
        ----------
        feature : SlidingWindowFeature
            Pre-extracted features
        """

        focus = feature.getExtent()

        sliding_window = SlidingWindow(
            duration=self.duration,
            step=self.step,
            start=focus.start, end=focus.end)

        for left in sliding_window:

            right = Segment(
                start=left.end,
                end=left.end + self.duration + self.gap
            )
            middle = .5*(left.end + right.start)

            yield middle, self.diff(left, right, feature)

    def apply(self, feature):

        x, y = zip(*[
            (m, d) for m, d in self.iterdiff(feature)
        ])
        x = np.array(x)
        y = np.array(y)

        # find local maxima
        maxima = scipy.signal.argrelmax(y)
        x = x[maxima]
        y = y[maxima]

        # only keep high enough local maxima
        high_maxima = np.where(y > self.threshold)

        # create list of segment boundaries
        # do not forget very first and last boundaries
        extent = feature.getExtent()
        boundaries = itertools.chain(
            [extent.start], x[high_maxima], [extent.end]
        )

        # create list of segments from boundaries
        segments = [Segment(*p) for p in pairwise(boundaries)]

        # TODO: find a way to set 'uri'
        return Timeline(segments=segments, uri=None)


class GaussianDivergenceMixin:

    def diff(self, left, right, feature):
        """Compute diagonal gaussian divergence between left and right windows

        Parameters
        ----------
        left, right : Segment
            Left and right window
        feature : Feature

        Returns
        -------
        divergence : float
            Gaussian divergence between left and right windows
        """

        gl = Gaussian(covariance_type='diag')
        Xl = feature.crop(left)
        gl.fit(Xl)

        gr = Gaussian(covariance_type='diag')
        Xr = feature.crop(right)
        gr.fit(Xr)

        try:
            divergence = gl.divergence(gr)
        except:
            divergence = np.NaN

        return divergence


class SegmentationGaussianDivergence(GaussianDivergenceMixin, SlidingWindowsSegmentation):
    pass
