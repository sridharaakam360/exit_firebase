-- MySQL dump 10.13  Distrib 8.0.41, for Win64 (x86_64)
--
-- Host: localhost    Database: pharmacy_app
-- ------------------------------------------------------
-- Server version	9.2.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `institution_students`
--

DROP TABLE IF EXISTS `institution_students`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `institution_students` (
  `id` int NOT NULL AUTO_INCREMENT,
  `institution_id` int NOT NULL,
  `user_id` int NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `institution_id` (`institution_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `institution_students_ibfk_1` FOREIGN KEY (`institution_id`) REFERENCES `institutions` (`id`),
  CONSTRAINT `institution_students_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `institution_students`
--

LOCK TABLES `institution_students` WRITE;
/*!40000 ALTER TABLE `institution_students` DISABLE KEYS */;
INSERT INTO `institution_students` VALUES (1,1,4,'2025-04-15 05:28:36'),(2,1,5,'2025-04-15 05:28:36'),(3,1,6,'2025-04-15 05:28:36'),(4,1,7,'2025-04-16 04:46:34'),(5,1,9,'2025-05-07 07:28:49');
/*!40000 ALTER TABLE `institution_students` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `institutions`
--

DROP TABLE IF EXISTS `institutions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `institutions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `institution_code` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `admin_id` int DEFAULT NULL,
  `subscription_plan_id` int DEFAULT NULL,
  `subscription_start` datetime DEFAULT NULL,
  `subscription_end` datetime DEFAULT NULL,
  `student_range` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `institution_code` (`institution_code`),
  UNIQUE KEY `email` (`email`),
  KEY `subscription_plan_id` (`subscription_plan_id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `institutions_ibfk_1` FOREIGN KEY (`subscription_plan_id`) REFERENCES `subscription_plans` (`id`),
  CONSTRAINT `institutions_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `institutions`
--

LOCK TABLES `institutions` WRITE;
/*!40000 ALTER TABLE `institutions` DISABLE KEYS */;
INSERT INTO `institutions` VALUES (1,'ABC001','ABC0014833','admin@abc.com',3,11,'2025-05-08 15:54:47','2025-06-07 15:54:47',30,'2025-04-15 05:27:13');
/*!40000 ALTER TABLE `institutions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `question_reviews`
--

DROP TABLE IF EXISTS `question_reviews`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `question_reviews` (
  `id` int NOT NULL AUTO_INCREMENT,
  `question_id` int NOT NULL,
  `user_id` int NOT NULL,
  `rating` int NOT NULL,
  `comment` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_question_review` (`user_id`,`question_id`),
  KEY `question_id` (`question_id`),
  CONSTRAINT `question_reviews_ibfk_1` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`),
  CONSTRAINT `question_reviews_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `question_reviews_chk_1` CHECK ((`rating` between 1 and 5))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `question_reviews`
--

LOCK TABLES `question_reviews` WRITE;
/*!40000 ALTER TABLE `question_reviews` DISABLE KEYS */;
/*!40000 ALTER TABLE `question_reviews` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `questions`
--

DROP TABLE IF EXISTS `questions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `questions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `question` text NOT NULL,
  `option_a` text NOT NULL,
  `option_b` text NOT NULL,
  `option_c` text NOT NULL,
  `option_d` text NOT NULL,
  `correct_answer` char(1) NOT NULL,
  `explanation` text,
  `difficulty` enum('easy','medium','hard') DEFAULT 'medium',
  `chapter` varchar(100) DEFAULT NULL,
  `subject_id` int NOT NULL,
  `is_previous_year` tinyint(1) DEFAULT '0',
  `previous_year` int DEFAULT NULL,
  `topics` json DEFAULT NULL,
  `created_by` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `subject_id` (`subject_id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `questions_ibfk_1` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`),
  CONSTRAINT `questions_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=51 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `questions`
--

LOCK TABLES `questions` WRITE;
/*!40000 ALTER TABLE `questions` DISABLE KEYS */;
INSERT INTO `questions` VALUES (1,'What is the primary purpose of a double-blind study?','To increase sample size','To reduce bias','To simplify data analysis','To shorten study duration','b','A double-blind study prevents both participants and researchers from knowing who is in the control or experimental group, reducing bias.','medium','Research Design',1,0,NULL,'[\"double-blind study\", \"bias reduction\"]',1,'2025-04-16 04:33:31'),(2,'Which statistical test is used to compare means of two groups?','Chi-square test','T-test','ANOVA','Regression analysis','b','The T-test is used to compare the means of two groups to determine if they are significantly different.','easy','Hypothesis Testing',1,0,NULL,'[\"t-test\", \"mean comparison\"]',1,'2025-04-16 04:33:31'),(3,'What does a p-value less than 0.05 indicate?','No significance','Statistical significance','Data error','High variability','b','A p-value < 0.05 suggests that the null hypothesis can be rejected, indicating statistical significance.','easy','Statistical Significance',1,0,NULL,'[\"p-value\", \"hypothesis testing\"]',1,'2025-04-16 04:33:31'),(4,'What is the purpose of a confidence interval?','To estimate population parameter','To reject null hypothesis','To calculate sample size','To determine correlation','a','A confidence interval provides a range of values likely to contain the population parameter.','medium','Estimation',1,0,NULL,'[\"confidence interval\", \"population parameter\"]',1,'2025-04-16 04:33:31'),(5,'Which measure of central tendency is most affected by extreme values?','Mean','Median','Mode','Midrange','a','The mean is sensitive to extreme values, unlike the median or mode.','easy','Descriptive Statistics',1,0,NULL,'[\"mean\", \"central tendency\"]',1,'2025-04-16 04:33:31'),(6,'What is the null hypothesis in a clinical trial?','No effect or difference','Significant effect','Positive correlation','Negative correlation','a','The null hypothesis assumes no effect or difference between groups.','medium','Hypothesis Testing',1,1,2023,'[\"null hypothesis\", \"clinical trial\"]',1,'2025-04-16 04:33:31'),(7,'What is a Type I error?','Rejecting a true null hypothesis','Accepting a false null hypothesis','Incorrect sample size','Data miscalculation','a','A Type I error occurs when a true null hypothesis is incorrectly rejected.','hard','Error Types',1,0,NULL,'[\"type I error\", \"hypothesis testing\"]',1,'2025-04-16 04:33:31'),(8,'What is the role of randomization in experiments?','Increase sample size','Reduce selection bias','Simplify calculations','Ensure normality','b','Randomization helps ensure groups are comparable, reducing selection bias.','medium','Research Design',1,0,NULL,'[\"randomization\", \"bias reduction\"]',1,'2025-04-16 04:33:31'),(9,'What is the primary goal of health education?','Prescribe medications','Promote health awareness','Perform surgeries','Diagnose diseases','b','Health education aims to inform and empower individuals to make healthy choices.','easy','Introduction to Health Education',2,0,NULL,'[\"health education\", \"awareness\"]',1,'2025-04-16 04:33:31'),(10,'Which is a key component of effective health communication?','Technical jargon','Clarity and simplicity','Lengthy explanations','Complex visuals','b','Clear and simple communication ensures the audience understands health messages.','medium','Communication Strategies',2,0,NULL,'[\"communication\", \"clarity\"]',1,'2025-04-16 04:33:31'),(11,'What is a common barrier to health education?','Access to technology','Cultural beliefs','High literacy','Clear messaging','b','Cultural beliefs can hinder the acceptance of health education messages.','medium','Barriers to Education',2,0,NULL,'[\"cultural beliefs\", \"barriers\"]',1,'2025-04-16 04:33:31'),(12,'Which disease prevention strategy is emphasized in health education?','Surgery','Vaccination','Antibiotic use','Radiation therapy','b','Vaccination is a key preventive measure promoted in health education.','easy','Disease Prevention',2,1,2022,'[\"vaccination\", \"prevention\"]',1,'2025-04-16 04:33:31'),(13,'What is the role of community in health education?','Funding research','Spreading awareness','Developing drugs','Conducting trials','b','Communities play a vital role in disseminating health education messages.','medium','Community Involvement',2,0,NULL,'[\"community\", \"health education\"]',1,'2025-04-16 04:33:31'),(14,'Which lifestyle change is most promoted for heart health?','High sugar intake','Regular exercise','Increased salt consumption','Smoking','b','Regular exercise is widely promoted to improve cardiovascular health.','easy','Lifestyle Changes',2,0,NULL,'[\"exercise\", \"heart health\"]',1,'2025-04-16 04:33:31'),(15,'What is the primary function of the skeletal system?','Digestion','Support and movement','Circulation','Respiration','b','The skeletal system provides structural support and enables movement.','easy','Skeletal System',3,0,NULL,'[\"skeletal system\", \"support\"]',1,'2025-04-16 04:33:31'),(16,'Which organ is primarily responsible for gas exchange?','Liver','Lungs','Kidneys','Stomach','b','The lungs facilitate the exchange of oxygen and carbon dioxide.','easy','Respiratory System',3,0,NULL,'[\"lungs\", \"gas exchange\"]',1,'2025-04-16 04:33:31'),(17,'What is the role of the autonomic nervous system?','Voluntary movement','Involuntary functions','Sensory processing','Memory storage','b','The autonomic nervous system controls involuntary functions like heart rate.','medium','Nervous System',3,0,NULL,'[\"autonomic nervous system\", \"involuntary\"]',1,'2025-04-16 04:33:31'),(18,'Which hormone regulates blood sugar levels?','Insulin','Adrenaline','Testosterone','Melatonin','a','Insulin, produced by the pancreas, lowers blood sugar levels.','medium','Endocrine System',3,1,2023,'[\"insulin\", \"blood sugar\"]',1,'2025-04-16 04:33:31'),(19,'What is the function of red blood cells?','Fight infection','Carry oxygen','Clot blood','Digest nutrients','b','Red blood cells transport oxygen from the lungs to the body tissues.','easy','Circulatory System',3,0,NULL,'[\"red blood cells\", \"oxygen transport\"]',1,'2025-04-16 04:33:31'),(20,'Which structure connects muscles to bones?','Ligament','Tendon','Cartilage','Fascia','b','Tendons are fibrous tissues that connect muscles to bones.','medium','Muscular System',3,0,NULL,'[\"tendon\", \"muscle connection\"]',1,'2025-04-16 04:33:31'),(21,'What is the primary role of the kidneys?','Blood filtration','Digestion','Vision','Hearing','a','The kidneys filter blood to remove waste and regulate fluid balance.','easy','Urinary System',3,0,NULL,'[\"kidneys\", \"filtration\"]',1,'2025-04-16 04:33:31'),(22,'What is the primary purpose of a pharmaceutical dosage form?','Enhance taste','Ensure accurate dosing','Reduce cost','Increase shelf life','b','Dosage forms ensure accurate delivery of the active drug to the body.','easy','Dosage Forms',4,0,NULL,'[\"dosage form\", \"drug delivery\"]',1,'2025-04-16 04:33:31'),(23,'Which dosage form is administered through the skin?','Tablet','Capsule','Transdermal patch','Syrup','c','Transdermal patches deliver drugs through the skin for systemic effects.','medium','Transdermal Systems',4,0,NULL,'[\"transdermal patch\", \"drug delivery\"]',1,'2025-04-16 04:33:31'),(24,'What is the main advantage of a sustained-release formulation?','Immediate effect','Reduced dosing frequency','Lower cost','Improved taste','b','Sustained-release formulations release drugs slowly, reducing dosing frequency.','medium','Controlled Release',4,1,2022,'[\"sustained release\", \"dosing\"]',1,'2025-04-16 04:33:31'),(25,'Which excipient is used to improve tablet disintegration?','Binder','Disintegrant','Lubricant','Sweetener','b','Disintegrants help tablets break apart in the digestive tract.','medium','Tablet Formulation',4,0,NULL,'[\"disintegrant\", \"tablet\"]',1,'2025-04-16 04:33:31'),(26,'What is the purpose of enteric coating on tablets?','Enhance taste','Protect stomach','Increase absorption','Reduce cost','b','Enteric coatings protect the stomach from irritation and the drug from acid.','hard','Tablet Coating',4,0,NULL,'[\"enteric coating\", \"protection\"]',1,'2025-04-16 04:33:31'),(27,'Which dosage form is suitable for pediatric patients?','Capsule','Injection','Syrup','Suppository','c','Syrups are often used for children due to ease of administration.','easy','Liquid Dosage Forms',4,0,NULL,'[\"syrup\", \"pediatric\"]',1,'2025-04-16 04:33:31'),(28,'What is the role of a preservative in liquid formulations?','Enhance flavor','Prevent microbial growth','Increase viscosity','Improve solubility','b','Preservatives inhibit microbial growth to ensure product safety.','medium','Formulation Stability',4,0,NULL,'[\"preservative\", \"microbial growth\"]',1,'2025-04-16 04:33:31'),(29,'Which process ensures uniform drug distribution in a tablet?','Granulation','Coating','Compression','Packaging','a','Granulation ensures uniform mixing of drug and excipients.','hard','Tablet Manufacturing',4,0,NULL,'[\"granulation\", \"uniformity\"]',1,'2025-04-16 04:33:31'),(30,'What is the main disadvantage of oral solutions?','Poor bioavailability','Short shelf life','High cost','Slow onset','b','Oral solutions often have a shorter shelf life due to stability issues.','medium','Liquid Dosage Forms',4,0,NULL,'[\"oral solution\", \"shelf life\"]',1,'2025-04-16 04:33:31'),(31,'What is the primary source of crude drugs in pharmacognosy?','Synthetic compounds','Plants','Minerals','Animals','b','Pharmacognosy primarily studies drugs derived from plant sources.','easy','Introduction to Pharmacognosy',5,0,NULL,'[\"crude drugs\", \"plants\"]',1,'2025-04-16 04:33:31'),(32,'Which plant part is used to obtain morphine?','Leaf','Root','Flower','Seed','c','Morphine is extracted from the opium poppy flower (capsule).','medium','Alkaloids',5,1,2023,'[\"morphine\", \"opium poppy\"]',1,'2025-04-16 04:33:31'),(33,'What is the role of secondary metabolites in plants?','Growth','Defense','Photosynthesis','Water transport','b','Secondary metabolites protect plants from pests and environmental stress.','medium','Plant Chemistry',5,0,NULL,'[\"secondary metabolites\", \"defense\"]',1,'2025-04-16 04:33:31'),(34,'Which method is used to extract essential oils from plants?','Filtration','Steam distillation','Crystallization','Precipitation','b','Steam distillation is commonly used to extract volatile essential oils.','medium','Extraction Techniques',5,0,NULL,'[\"essential oils\", \"steam distillation\"]',1,'2025-04-16 04:33:31'),(35,'What is the therapeutic use of ginseng?','Antibiotic','Energy enhancement','Pain relief','Anticoagulant','b','Ginseng is used to boost energy and improve overall vitality.','easy','Medicinal Plants',5,0,NULL,'[\"ginseng\", \"energy\"]',1,'2025-04-16 04:33:31'),(36,'What does ADME stand for in pharmacology?','Absorption, Distribution, Metabolism, Excretion','Analysis, Delivery, Modification, Elimination','Activation, Dispersion, Mutation, Extraction','Administration, Dissolution, Mobilization, Evacuation','a','ADME describes the pharmacokinetic processes of a drug in the body.','easy','Pharmacokinetics',6,0,NULL,'[\"ADME\", \"pharmacokinetics\"]',1,'2025-04-16 04:33:31'),(37,'Which process describes how a drug enters the bloodstream?','Metabolism','Absorption','Distribution','Excretion','b','Absorption is the process by which a drug enters the bloodstream.','easy','Absorption',6,0,NULL,'[\"absorption\", \"pharmacokinetics\"]',1,'2025-04-16 04:33:31'),(38,'What is the primary site of drug metabolism?','Kidneys','Liver','Lungs','Stomach','b','The liver is the main organ responsible for metabolizing drugs.','medium','Metabolism',6,1,2022,'[\"liver\", \"metabolism\"]',1,'2025-04-16 04:33:31'),(39,'Which factor affects drug distribution in the body?','Blood flow','Drug color','Tablet size','Packaging','a','Blood flow determines how a drug is distributed to tissues.','medium','Distribution',6,0,NULL,'[\"distribution\", \"blood flow\"]',1,'2025-04-16 04:33:31'),(40,'What is the term for the time it takes for half of a drug to be eliminated?','Half-life','Bioavailability','Clearance','Potency','a','The half-life is the time required for half of the drug to be eliminated.','medium','Excretion',6,0,NULL,'[\"half-life\", \"elimination\"]',1,'2025-04-16 04:33:31'),(41,'Which route of administration bypasses first-pass metabolism?','Oral','Intravenous','Sublingual','Rectal','b','Intravenous administration delivers the drug directly into the bloodstream.','hard','Administration Routes',6,0,NULL,'[\"intravenous\", \"first-pass metabolism\"]',1,'2025-04-16 04:33:31'),(44,'What does the term \"first-pass metabolism\" refer to?','Drug absorption in the stomach','Drug metabolism in the liver','Drug excretion in the kidneys','Drug distribution in tissues','b','First-pass metabolism occurs when a drug is metabolized in the liver before reaching circulation.','medium','Metabolism',6,1,2023,'[\"first-pass metabolism\", \"liver\"]',1,'2025-04-16 04:33:31'),(45,'Which parameter measures the rate of drug elimination?','Clearance','Potency','Efficacy','Affinity','a','Clearance measures the rate at which a drug is removed from the body.','hard','Excretion',6,0,NULL,'[\"clearance\", \"elimination\"]',1,'2025-04-16 04:33:31'),(46,'Which drug is used to treat hypertension?','Aspirin','Lisinopril','Ibuprofen','Paracetamol','B','Lisinopril is an ACE inhibitor used to treat hypertension.','medium','Pharmacology',6,1,2023,'[\"hypertension\", \" drugs\"]',NULL,'2025-05-10 06:07:43'),(47,'Which drug is used to treat hypertension?','Aspirin','Lisinopril','Ibuprofen','Paracetamol','B','Lisinopril is an ACE inhibitor used to treat hypertension.','medium','Pharmacology',5,1,2023,'[\"hypertension\", \" drugs\"]',NULL,'2025-05-10 06:10:16'),(48,'Which drug is used to treat hypertension?','Aspirin','Lisinopril','Ibuprofen','Paracetamol','B','Lisinopril is an ACE inhibitor used to treat hypertension.','medium','Pharmacology',6,1,2023,'[\"hypertension\", \" drugs\"]',NULL,'2025-05-10 06:11:46'),(49,'What is the primary source of energy for Earth\'s climate system?','The Sun','Geothermal energy','Nuclear energy','Wind energy','A','The Sun provides the primary energy for Earth\'s climate system through solar radiation.','easy','Environmental Science',1,0,NULL,'[\"climate\", \" energy\"]',NULL,'2025-05-10 06:16:04'),(50,'Which drug is used to treat hypertension?','Aspirin','Lisinopril','Ibuprofen','Paracetamol','B','Lisinopril is an ACE inhibitor used to treat hypertension.','medium','Pharmacology',1,1,2023,'[\"hypertension\", \" drugs\"]',NULL,'2025-05-10 06:16:04');
/*!40000 ALTER TABLE `questions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `results`
--

DROP TABLE IF EXISTS `results`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `results` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `subject_id` int NOT NULL,
  `score` int NOT NULL,
  `total_questions` int NOT NULL,
  `time_taken` int NOT NULL,
  `answers` json DEFAULT NULL,
  `date_taken` datetime NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `subject_id` (`subject_id`),
  CONSTRAINT `results_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `results_ibfk_2` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `results`
--

LOCK TABLES `results` WRITE;
/*!40000 ALTER TABLE `results` DISABLE KEYS */;
INSERT INTO `results` VALUES (1,1,2,17,6,20,'{\"9\": \"a\", \"10\": \"c\", \"11\": \"d\", \"12\": \"b\", \"13\": \"c\", \"14\": \"c\"}','2025-04-16 10:06:31','2025-04-16 04:36:31'),(2,1,3,0,7,2,'{\"17\": null}','2025-04-16 10:07:18','2025-04-16 04:37:18'),(3,1,3,0,7,6,'{\"15\": null, \"16\": null, \"17\": null, \"18\": null, \"19\": null, \"20\": null, \"21\": null}','2025-04-16 10:07:40','2025-04-16 04:37:40'),(4,1,3,29,7,19,'{\"15\": \"a\", \"16\": \"a\", \"17\": \"a\", \"18\": \"a\", \"19\": \"a\", \"20\": \"a\", \"21\": \"a\"}','2025-04-16 10:08:14','2025-04-16 04:38:14'),(5,2,3,71,7,44,'{\"15\": \"b\", \"16\": \"b\", \"17\": \"a\", \"18\": \"a\", \"19\": \"b\", \"20\": \"a\", \"21\": \"a\"}','2025-04-16 10:11:19','2025-04-16 04:41:19'),(6,2,6,100,2,15,'{\"38\": \"b\", \"44\": \"b\"}','2025-04-16 10:12:21','2025-04-16 04:42:21'),(7,4,2,0,6,4,'{\"12\": \"a\"}','2025-04-16 10:15:46','2025-04-16 04:45:46'),(8,8,3,71,7,25,'{\"15\": \"b\", \"16\": \"b\", \"17\": null, \"18\": \"a\", \"19\": \"a\", \"20\": \"b\", \"21\": \"a\"}','2025-05-07 08:32:45','2025-05-07 03:02:45'),(9,8,3,0,7,13,'{\"16\": null, \"17\": null, \"18\": \"b\", \"19\": null, \"20\": null, \"21\": null}','2025-05-07 08:35:17','2025-05-07 03:05:17'),(10,8,3,0,7,86,'{\"15\": \"c\", \"16\": \"c\", \"17\": null, \"18\": null, \"19\": null, \"20\": null, \"21\": null}','2025-05-07 08:37:20','2025-05-07 03:07:20'),(11,2,6,50,2,9,'{\"40\": null, \"45\": \"a\"}','2025-05-07 08:53:42','2025-05-07 03:23:42'),(12,3,1,0,8,6,'{\"1\": null, \"2\": null, \"4\": null, \"7\": null, \"8\": null}','2025-05-07 13:08:36','2025-05-07 07:38:36'),(13,3,3,43,7,20,'{\"15\": \"c\", \"16\": \"b\", \"17\": \"a\", \"18\": \"a\", \"19\": \"b\", \"20\": \"a\", \"21\": \"c\"}','2025-05-07 13:11:49','2025-05-07 07:41:49'),(14,2,5,0,5,24,'{\"31\": null, \"32\": null, \"33\": \"a\", \"34\": null, \"35\": null}','2025-05-07 13:43:52','2025-05-07 08:13:52'),(15,2,4,22,9,60,'{\"22\": null, \"23\": \"c\", \"24\": null, \"25\": \"a\", \"26\": \"a\", \"27\": \"c\", \"28\": \"a\", \"29\": \"d\", \"30\": \"d\"}','2025-05-07 13:54:02','2025-05-07 08:24:02'),(16,9,3,100,1,4,'{\"18\": \"a\"}','2025-05-08 15:58:27','2025-05-08 10:28:27');
/*!40000 ALTER TABLE `results` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subjects`
--

DROP TABLE IF EXISTS `subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subjects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `degree_type` enum('Dpharm','Bpharm') NOT NULL,
  `description` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subjects`
--

LOCK TABLES `subjects` WRITE;
/*!40000 ALTER TABLE `subjects` DISABLE KEYS */;
INSERT INTO `subjects` VALUES (1,'Human Anatomy & Physiology','Dpharm','Structure and functions of Body','2025-04-16 04:22:54'),(2,'Health Education','Dpharm','Education about our Health','2025-04-16 04:23:34'),(3,'Pharmacognosy-I','Dpharm','Plant study','2025-04-16 04:24:13'),(4,'Pharmacology I','Bpharm','ADME properties','2025-04-16 04:24:55'),(5,'Pharmaceutics I','Bpharm','Dosage Forms','2025-04-16 04:25:13'),(6,'Biostatistics & Research methodology','Bpharm','Research statistics','2025-04-16 04:26:38');
/*!40000 ALTER TABLE `subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subscription_history`
--

DROP TABLE IF EXISTS `subscription_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subscription_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `subscription_plan_id` int NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `amount_paid` decimal(10,2) NOT NULL,
  `payment_method` varchar(50) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `subscription_plan_id` (`subscription_plan_id`),
  CONSTRAINT `subscription_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `subscription_history_ibfk_2` FOREIGN KEY (`subscription_plan_id`) REFERENCES `subscription_plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subscription_history`
--

LOCK TABLES `subscription_history` WRITE;
/*!40000 ALTER TABLE `subscription_history` DISABLE KEYS */;
INSERT INTO `subscription_history` VALUES (1,2,1,'2025-04-15','2025-05-15',100.00,'credit_card','2025-04-15 05:31:13'),(3,2,1,'2025-04-16','2025-05-16',100.00,'credit_card','2025-04-16 04:40:22'),(5,8,1,'2025-05-07','2025-06-06',100.00,'credit_card','2025-05-07 03:02:08'),(6,3,5,'2025-05-07','2025-07-06',1000.00,'institution','2025-05-07 04:49:15'),(8,3,5,'2025-05-07','2025-07-06',1000.00,'institution','2025-05-07 05:06:13'),(10,3,11,'2025-05-08','2025-06-07',500.00,'institution','2025-05-08 07:05:56'),(11,3,5,'2025-05-08','2025-07-07',0.00,'institution','2025-05-08 07:06:15'),(12,3,11,'2025-05-08','2025-06-07',500.00,'institution','2025-05-08 10:24:47'),(13,2,1,'2025-05-08','2025-06-07',0.00,'mock','2025-05-08 10:56:29'),(16,2,1,'2025-05-08','2025-06-07',0.00,'mock','2025-05-08 11:04:09');
/*!40000 ALTER TABLE `subscription_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `subscription_plans`
--

DROP TABLE IF EXISTS `subscription_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subscription_plans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `duration_months` int NOT NULL,
  `description` text,
  `degree_access` enum('Dpharm','Bpharm','both') NOT NULL,
  `is_active` int DEFAULT NULL,
  `includes_previous_years` tinyint(1) DEFAULT '1',
  `is_institution` tinyint(1) DEFAULT '0',
  `student_range` int DEFAULT NULL,
  `custom_student_range` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `subscription_plans`
--

LOCK TABLES `subscription_plans` WRITE;
/*!40000 ALTER TABLE `subscription_plans` DISABLE KEYS */;
INSERT INTO `subscription_plans` VALUES (1,'Free Plan',0.00,1,NULL,'Dpharm',1,0,0,NULL,0,'2025-04-15 04:15:39'),(5,'Free Institute',0.00,2,NULL,'Dpharm',1,0,1,NULL,0,'2025-04-15 04:52:34'),(11,'Institute plan 1',500.00,1,'Institute plan 1','Dpharm',1,0,1,30,NULL,'2025-05-08 07:04:36');
/*!40000 ALTER TABLE `subscription_plans` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('individual','student','instituteadmin','superadmin') NOT NULL,
  `subscription_plan_id` int DEFAULT NULL,
  `subscription_start` datetime DEFAULT NULL,
  `subscription_end` datetime DEFAULT NULL,
  `subscription_status` enum('active','expired','cancelled') DEFAULT 'expired',
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_active` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  KEY `users_ibfk_1` (`subscription_plan_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`subscription_plan_id`) REFERENCES `subscription_plans` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'superadmin','superadmin@gmail.com','scrypt:32768:8:1$DYpOTWKVIjEk2Yrv$378e403559dc98731a8ad681fee66642cb0957b213687f9e6b63c31b9f32ed1a0406d475d7d34bcd6285394b95505117f8fe0d3b14015bef2387bbe2e9dbce49','superadmin',1,NULL,NULL,'expired','active','2025-04-14 10:05:10',NULL),(2,'Thara123','p20bp101l@shanmugha.edu.in','scrypt:32768:8:1$nhjwLm13yZG3JJB7$39a65e3b6be736f0809edc862c2b90bfd373a83a358f7953173c8fea28dd82da787100c59a150a347122cc2c06de85148caecfecd7bf278dbc2224985933ce3d','individual',1,NULL,NULL,'expired','active','2025-04-15 04:16:45','2025-05-08 10:35:14'),(3,'admin@abc','admin@abc.com','scrypt:32768:8:1$yQsiVssSBomFAyaN$3956e796ff860e3e11122c812c1768dc4ed20971fa724d6c05b31312a99260536b55b6348ea9812dc7bb1246db2ec396010d8a8de6d03cabed4656d67dcea11a','instituteadmin',11,NULL,NULL,'expired','active','2025-04-15 05:27:13',NULL),(4,'john_student','john@example.com','scrypt:32768:8:1$A4CJj5iQmLxclEe9$c113b970d7aa47cdbd06d9f8c3e927478e724ff72bfd0b47145cd34efd77333028ba3de7d04b7f46f2281c1d94a5b26ea2d3d3cf0b41797013dbf93ffab9981d','student',1,NULL,NULL,'expired','active','2025-04-15 05:28:36','2025-04-15 10:58:36'),(5,'sarah_smith','sarah@example.com','scrypt:32768:8:1$oHMK2blyIMaWz75m$e4a81f7f556c92339d52833cbec708c244c44ad1228afc40cd4cb6698af81f47bd5d085e270aa07c00cfed70196d4f0058fcfed9641469de4b7232497d23ad18','student',1,NULL,NULL,'expired','active','2025-04-15 05:28:36','2025-04-15 10:58:36'),(6,'michael_brown','michael@example.com','scrypt:32768:8:1$kBRucgu3zWij0Den$83dd19c9761948581bdd133f6ecacec7cf685295ff0301d45ab6447a6a2a8e7213fe242ca6f0daa21261f01c26b44014a6b8e397ee5a8fd7bf302cd9f75b9102','student',1,NULL,NULL,'expired','active','2025-04-15 05:28:36','2025-04-15 10:58:36'),(7,'student1','student1@gmail.com','scrypt:32768:8:1$sEipmeUMvoH4FLG1$fa9a404da09351b26badf151f3b87f5758453657c400d7fdf9a6d9cccdee39e171b56d0194e8656568425449d2234c71174d199b6b08f0b020b165e5d338ef77','student',1,NULL,NULL,'expired','active','2025-04-16 04:46:34',NULL),(8,'john','john@123.com','scrypt:32768:8:1$SbJXJF5TgMQ410Hy$cd220657355cb3e9b78c2174727033ffaff1abe5017fe8da5c4f660cc8aa1895fc98645a28c93709b36c26720adca7cf881930a9d94f155b132ba44e0302b184','superadmin',1,'2025-05-07 00:00:00','2025-06-06 00:00:00','active','active','2025-05-07 03:01:15','2025-05-07 08:32:09'),(9,'mukesh','mukesh@123.com','scrypt:32768:8:1$0EAPPtQ75oRHxwaQ$b72b7a0d238a5bc7634adc6e387c048281c36f084c5f89926ef052fa58cfcb3755c258ce6c80e28a196f11fde823b5d6f1eee792d18ae786c3dd9d41b838afa3','student',1,NULL,NULL,'expired','active','2025-05-07 07:28:49',NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-05-10 17:03:49
