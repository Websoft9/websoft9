// @flow
import { all } from 'redux-saga/effects';

import layoutSaga from './layout/saga';

export default function* rootSaga(): any {
    yield all([layoutSaga()]);
}
