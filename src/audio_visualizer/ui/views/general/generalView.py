'''
MIT License

Copyright (c) 2025 Timothy Eck

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

from PySide6.QtWidgets import (
    QLayout, QWidget, QGridLayout
)


class View:

    def __init__(self):
        self.layout = QGridLayout()
        self.controler = QWidget()

    '''
    Returns the widgets of this view nested within a single layout.
    '''
    def get_view_in_layout(self) -> QLayout:
        return self.layout
    
    '''
    Returns the widgets of this view nested within a single parent widget.
    '''
    def get_view_in_widget(self) -> QWidget:
        return self.controler
    
    '''
    Verifies that the input values in the view are valide.
    '''
    def validate_view(self) -> bool:
        raise NotImplementedError("Subclasses should implement this method.")
    
    '''
    Transforms the input values in the view into a python object.
    '''
    def read_view_values(self) -> object:
        raise NotImplementedError("Subclasses should implement this method.")



