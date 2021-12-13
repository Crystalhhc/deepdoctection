# -*- coding: utf-8 -*-
# File: tpdoctectionpipe.py

# Copyright 2021 Dr. Janis Meyer. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module for pipeline with Tensorpack predictors
"""

import os
from typing import Optional, Union, Dict, List
from ..mapper.utils import cur
from ..datapoint.image import Image
from ..dataflow import DataFlow, MapData  # type: ignore
from ..dataflow.custom_serialize import SerializerFiles, SerializerPdfDoc
from ..mapper.misc import to_image
from ..mapper.pagestruct import to_page
from .base import Pipeline

__all__ = ["DoctectionPipe"]


class DoctectionPipe(Pipeline):  # pylint: disable=W0221
    """
    Prototype for a document layout pipeline. Contains implementation for loading document types (images in directory,
    single PDF document, dataflow from datasets), conversions in dataflows and building a pipeline.

    See deep_doctection.analyzer.dd for a concrete implementation.

    See also the explanations in :class:`base.Pipeline`
    """

    def _entry(self, **kwargs: str) -> DataFlow:
        dataset_dataflow = kwargs.get("dataset_dataflow")
        path = kwargs.get("path")
        file_type = kwargs.get("file_type", [".jpg", ".png"])
        doc_path = kwargs.get("doc_path")
        max_datapoints = kwargs.get("max_datapoints")

        assert (path is None or doc_path is None) or (
            path is not None or doc_path is not None
        ), "pass either path to image dir or pdf doc but not both"
        assert path is not None or doc_path is not None or dataset_dataflow is not None, (
            "path either dataset " "dataflow or path or " "doc_path with arguments"
        )

        if isinstance(path, str):
            df = DoctectionPipe.path_to_dataflow(path, file_type)
        if isinstance(doc_path, str):
            df = DoctectionPipe.doc_to_dataflow(
                path=doc_path, max_datapoints=int(max_datapoints) if max_datapoints is not None else None
            )
        if dataset_dataflow is not None:
            df = dataset_dataflow

        return df

    @staticmethod
    def path_to_dataflow(path: str, file_type: Union[str, List[str]], max_datapoints: Optional[int] = None) -> DataFlow:
        """
        Processing method for directories

        :param path: path to directory
        :param file_type: file type to consider (single str or list of strings)
        :param max_datapoints: max number of datapoints to consider
        :return: dataflow
        """
        assert os.path.isdir(path), f"{path} not a directory"
        df = SerializerFiles.load(path, file_type, max_datapoints)

        def _to_image(dp: str) -> Optional[Image]:
            _, file_name = os.path.split(dp)
            print(f"processing {file_name}")
            dp = {"file_name": file_name, "location": dp}  # type: ignore
            return to_image(dp)

        df = MapData(df, _to_image)
        return df

    @staticmethod
    def doc_to_dataflow(path: str, max_datapoints: Optional[int] = None) -> DataFlow:
        """
        Processing method for documents

        :param path: path to directory
        :param max_datapoints: max number of datapoints to consider
        :return: dataflow
        """
        assert os.path.isfile(path), f"{path} not a file"
        df = SerializerPdfDoc.load(path, max_datapoints=max_datapoints)

        @cur  # type: ignore
        def _to_image(dp: Union[str, Dict[str, Union[str, bytes]]], dpi: Optional[int] = None) -> Optional[Image]:
            print(f"processing {dp['file_name']}")  # type: ignore
            return to_image(dp, dpi)

        df = MapData(df, _to_image(dpi=300))  # type: ignore  # pylint: disable=E1120
        return df

    @staticmethod
    def dataflow_to_page(df: DataFlow) -> DataFlow:
        """
        Converts a dataflow of images to a dataflow of pages

        :param df: Dataflow
        :return: Dataflow
        """
        return MapData(df, to_page)

    def analyze(self, **kwargs: str) -> DataFlow:
        """
        :param kwargs key dataset_dataflow: Transfer a dataflow of a dataset via its dataflow builder
        :param kwargs key path: A path to a directory in which either image documents or pdf files are located. It is
                                assumed that the pdf documents consist of only one page. If there are multiple pages,
                                only the first page is processed through the pipeline.
        :param kwargs key file_type: Selection of the file type, if: args: `path` is passed
        :param kwargs key doc_path: A path to a PDF document
        :param kwargs key max_datapoints: Stops processing as soon as max_datapoints images have been processed
        :return: dataflow
        """

        output = kwargs.get("output", "page")
        assert output in ["page", "image", "dict"], "output must be either page image or dict"
        df = self._entry(**kwargs)
        df = self._build_pipe(df)
        if output == "page":
            df = self.dataflow_to_page(df)
        elif output == "dict":
            df = self.dataflow_to_page(df)
            df = MapData(df, lambda dp: dp.as_dict())
        return df