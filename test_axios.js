import axios from 'axios'
const client = axios.create({ baseURL: 'https://test.com/api/v1' })
console.log(client.defaults.baseURL)
