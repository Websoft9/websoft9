import { ApolloClient, ApolloProvider, HttpLink, InMemoryCache } from '@apollo/client';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import App from './App';
import config from "./config";
import { configureStore } from './redux/store';

const token = config.ACCESS_TOKEN;
const spaces = config.SPACES;

const link = new HttpLink({
  uri: `https://graphql.contentful.com/content/v1/spaces/${spaces}`,
  headers: {
    authorization: `Bearer ${token}`,
  },
});

const client = new ApolloClient({
  cache: new InMemoryCache(),
  link,
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ApolloProvider client={client}>
      <Provider store={configureStore({})}>
        <App />
      </Provider>
    </ApolloProvider>
  </React.StrictMode>
);