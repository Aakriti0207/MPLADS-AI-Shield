import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import ProjectDetails from './pages/ProjectDetails'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import MapPage from './pages/MapPage'
import Reports from './pages/Reports'

export default function App(){
  return <Routes>
    <Route path="/" element={<Home/>}/>
    <Route path="/login" element={<Login/>}/>
    <Route element={<Layout/>}>
      <Route path="/dashboard" element={<Dashboard/>}/>
      <Route path="/projects" element={<Projects/>}/>
      <Route path="/projects/:id" element={<ProjectDetails/>}/>
      <Route path="/alerts" element={<Alerts/>}/>
      <Route path="/analytics" element={<Analytics/>}/>
      <Route path="/map" element={<MapPage/>}/>
      <Route path="/reports" element={<Reports/>}/>
    </Route>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Routes>
}