import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
const router=createRouter({history:createWebHistory(),routes:[
 {path:'/',component:()=>import('./views/Dashboard.vue')},
 {path:'/fund/:code',component:()=>import('./views/FundDetail.vue')},
 {path:'/fund/:code/holding',component:()=>import('./views/Holdings.vue')},
 {path:'/market',component:()=>import('./views/Market.vue')},
 {path:'/anomalies',component:()=>import('./views/Anomalies.vue')},
]})
createApp(App).use(router).mount('#app')
